import os
import io
import sys
import json
import time
import uuid
import asyncio
import logging
import threading
import subprocess
import PIL.Image
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from .grammar import CrochetGrammar
    from .geometry import GeometryEngine
    from .vision import analyze_with_retry
    from . import comfyui, mesh_measure
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from grammar import CrochetGrammar
    from geometry import GeometryEngine
    from vision import analyze_with_retry
    import comfyui, mesh_measure

try:
    from data.database import get_db, insert_feedback, get_feedback_stats, get_unincorporated_count
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

RETRAIN_THRESHOLD = int(os.environ.get("RETRAIN_THRESHOLD", "100"))

logger = logging.getLogger(__name__)

app = FastAPI()
geo = GeometryEngine()

_UPLOADS_DIR = os.path.join(PROJECT_ROOT, "backend", "output", "uploads")
_MODELS_DIR = os.path.join(PROJECT_ROOT, "backend", "output", "models")
os.makedirs(_UPLOADS_DIR, exist_ok=True)
os.makedirs(_MODELS_DIR, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(PROJECT_ROOT, "frontend", "static")),
    name="static",
)
app.mount("/models", StaticFiles(directory=_MODELS_DIR), name="models")


@app.on_event("startup")
async def _startup():
    comfyui.check_node()
    comfyui.start()


@app.on_event("shutdown")
async def _shutdown():
    comfyui.stop()


# ─── Mesh-measurement async job tracker ───────────────────────────────────────

_measure_jobs: dict = {}
_MEASURE_JOB_TTL_SECONDS = 3600


def _measure_evict_expired() -> None:
    cutoff = time.time() - _MEASURE_JOB_TTL_SECONDS
    for sid in [s for s, j in _measure_jobs.items() if j.get("created_at", 0) < cutoff]:
        del _measure_jobs[sid]


def _measure_create(session_id: str) -> None:
    _measure_evict_expired()
    _measure_jobs[session_id] = {
        "status": "pending", "parts": None, "error": None, "created_at": time.time(),
    }


def _measure_update(session_id: str, **kwargs) -> None:
    if session_id in _measure_jobs:
        _measure_jobs[session_id].update(kwargs)


def _measure_get(session_id: str):
    return _measure_jobs.get(session_id)


def _measure_sync(parts_in: list, glb_path: str, grammar) -> list:
    """Blocking measurement work — runs off the event loop via to_thread.

    Two-pass: measure raw diameters per part first, then calibrate them
    against the hardcoded diameters' max so they land in the grammar's
    expected cm-like range while preserving relative proportions from the mesh.
    Hunyuan3D meshes have no absolute scale, so the calibration is essential —
    without it every measured part becomes a degenerate 6-stitch tube.
    """
    mesh = mesh_measure.load_normalized_mesh(glb_path)

    # Pass 1: measure each measurable part's raw mesh diameters.
    raw = []  # list of (part_in_dict, measured_or_None)
    for p in parts_in:
        bbox = p.get("bbox")
        ptype = p.get("primitive_type") or "sphere"
        if not bbox or ptype == "flat_disc":
            raw.append((p, None))
            continue
        measured = mesh_measure.measure_part(mesh, bbox)
        if not mesh_measure._is_reasonable(measured, len(measured)):
            raw.append((p, None))
            continue
        raw.append((p, measured))

    # Calibration: align the measured max to the hardcoded max.
    measured_max = max((max(m) for _, m in raw if m), default=0.0)
    hardcoded_max = max((max(p["diameters"]) for p, _ in raw if p.get("diameters")), default=0.0)
    scale = (hardcoded_max / measured_max) if (measured_max > 0 and hardcoded_max > 0) else 1.0

    # Pass 2: recompile through grammar with calibrated diameters.
    refined = []
    for p, measured in raw:
        ptype = p.get("primitive_type") or "sphere"
        if measured is None:
            refined.append({
                "name": p["name"],
                "instructions": p["instructions"],
                "diameters": list(p["diameters"]),
                "primitive_type": ptype,
            })
            continue
        calibrated = [d * scale for d in measured]
        instrs = grammar.compile_part(p["name"], calibrated, primitive_type=ptype)
        rounds_used = sum(1 for line in instrs if line.startswith(("Rnd ", "Row ")))
        eff = calibrated[:rounds_used] if rounds_used else calibrated
        refined.append({
            "name": p["name"],
            "instructions": instrs,
            "diameters": [float(d) for d in eff],
            "primitive_type": ptype,
        })
    return refined


async def _measure_after_mesh(session_id, parts_in, glb_path, grammar):
    """Wait for the .glb, then run measurement off-thread and store the result."""
    for _ in range(150):  # ~10 min at 4s
        job = comfyui.get_job(session_id)
        if job and job["status"] == "done":
            break
        if job and job["status"] == "failed":
            _measure_update(session_id, status="failed", error="3D mesh generation failed")
            return
        await asyncio.sleep(4)
    else:
        _measure_update(session_id, status="failed", error="timed out waiting for 3D mesh")
        return
    if not os.path.exists(glb_path):
        _measure_update(session_id, status="failed", error="3D mesh file missing")
        return
    _measure_update(session_id, status="running")
    try:
        refined = await asyncio.to_thread(_measure_sync, parts_in, glb_path, grammar)
        _measure_update(session_id, status="done", parts=refined)
    except Exception as exc:
        _measure_update(session_id, status="failed", error=str(exc))


class PatternResponse(BaseModel):
    name: str
    instructions: List[str]
    diameters: List[float]
    primitive_type: Optional[str] = None


class FeedbackRequest(BaseModel):
    session_id: str
    part_name: str
    primitive_type: Optional[str] = None
    original_diameters: List[float]
    corrected_diameters: List[float]
    notes: Optional[str] = None


# Runs in a threadpool (sync BackgroundTasks), so guard with a threading lock:
# two feedback submissions near the threshold must not spawn concurrent trainings.
_retrain_lock = threading.Lock()
_retrain_process: Optional[subprocess.Popen] = None


def _maybe_trigger_retraining():
    global _retrain_process
    if not DB_AVAILABLE:
        return
    try:
        with get_db() as conn:
            count = get_unincorporated_count(conn)
        if count < RETRAIN_THRESHOLD:
            return
        with _retrain_lock:
            if _retrain_process is not None and _retrain_process.poll() is None:
                logger.info(
                    "Retraining already running (PID %d) — skipping trigger",
                    _retrain_process.pid,
                )
                return
            _retrain_process = subprocess.Popen(
                [sys.executable, "-m", "models.train", "--all"], cwd=PROJECT_ROOT
            )
            logger.info(
                "Spawned retraining (PID %d) — %d unincorporated corrections",
                _retrain_process.pid, count,
            )
    except Exception as exc:
        logger.warning("Retraining trigger failed: %s", exc)


GEMINI_PROMPT = (
    "Analyze this doll/amigurumi photo and deconstruct it into 3D geometric primitives for crochet. "
    "Identify the main parts (e.g. Head, Body, Left Arm, Right Leg, Ear, Tail) and categorize each "
    "part's base shape using exactly one of these types:\n"
    "  sphere    – round, ball-like shapes (head, round body)\n"
    "  cylinder  – straight, uniform-width tubes (neck, straight limb)\n"
    "  cone      – shapes that taper from narrow to wide (beak, horn, pointed ear)\n"
    "  frustum   – boxy shape that widens then holds flat (torso, foot)\n"
    "  capsule   – cylinder with rounded ends (plush limb, sausage body)\n"
    "  teardrop  – pear-shaped, wide at one end (pear body, raindrop snout)\n"
    "  flat_disc – thin flat circle (flat ear, hat brim, button nose)\n"
    "  torus     – ring/donut shape (bracelet, collar ring)\n"
    "IMPORTANT: Parts named arm, leg, paw, or flipper MUST use capsule or cylinder, NEVER sphere.\n"
    "IMPORTANT: Parts named ear, wing, or fin MUST use flat_disc, NEVER cone or sphere.\n"
    "Provide a relative scale for each part (1.0 = medium, 2.0 = twice as large).\n"
    "Also include a 'bbox' field per part: a normalized 2D bounding box "
    "[x_min, y_min, x_max, y_max], each float in [0, 1] in image coordinates "
    "(image-y points DOWN — y=0 is the top of the image, y=1 is the bottom). "
    "The bbox should tightly enclose the part as visible in the photo."
)

_LIMB_KEYWORDS = {"ARM", "LEG", "PAW", "FLIPPER"}
_EAR_KEYWORDS = {"EAR", "WING", "FIN"}


def _coerce_limb_types(graph: list) -> list:
    for part in graph:
        name_upper = part.get("name", "").upper()
        if part.get("type") == "sphere" and any(kw in name_upper for kw in _LIMB_KEYWORDS):
            part["type"] = "capsule"
        if part.get("type") != "flat_disc" and any(kw in name_upper for kw in _EAR_KEYWORDS):
            part["type"] = "flat_disc"
    return graph


@app.get("/preview/{session_id}")
async def preview_status(session_id: str):
    job = comfyui.get_job(session_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return job


@app.get("/measured/{session_id}")
async def measured_status(session_id: str):
    job = _measure_get(session_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No measurement job for this session")
    return job


@app.post("/generate", response_model=List[PatternResponse])
async def generate_pattern(
    file: UploadFile = File(...),
    gauge_stitches_per_10cm: Optional[float] = Form(None),
    gauge_rows_per_10cm: Optional[float] = Form(None),
    session_id: Optional[str] = Form(None),
):
    if not session_id:
        session_id = str(uuid.uuid4())

    sw = (10.0 / gauge_stitches_per_10cm) if gauge_stitches_per_10cm else 1.0
    sh = (10.0 / gauge_rows_per_10cm) if gauge_rows_per_10cm else 1.0
    grammar = CrochetGrammar(stitch_width_cm=sw, stitch_height_cm=sh)

    try:
        image_data = await file.read()

        # Persist image for async 3D generation job
        upload_path = os.path.join(_UPLOADS_DIR, f"{session_id}.jpg")
        image = PIL.Image.open(io.BytesIO(image_data))
        image.convert("RGB").save(upload_path, format="JPEG")
        img_io = io.BytesIO()
        image.convert("RGB").save(img_io, format="JPEG")
        img_bytes = img_io.getvalue()

        # Vision call is synchronous (network roundtrip + retries) — run it off
        # the event loop so preview/measure polling stays responsive.
        analysis = await asyncio.to_thread(analyze_with_retry, img_bytes, GEMINI_PROMPT)
        graph = _coerce_limb_types(analysis.get("parts", []))

        # Stash bboxes by part name for the mesh-measurement coordinator.
        bboxes = {p.get("name"): p.get("bbox") for p in graph if p.get("bbox")}

        parts_data = geo.process_dependency_graph(graph)

        results = []
        for part in parts_data:
            instructions = grammar.compile_part(part["name"], part["diameters"], primitive_type=part.get("type", "sphere"))
            rounds_used = sum(1 for line in instructions if line.startswith(("Rnd ", "Row ")))
            effective_diameters = part["diameters"][:rounds_used] if rounds_used else part["diameters"]
            results.append(PatternResponse(
                name=part["name"],
                instructions=instructions,
                diameters=effective_diameters,
                primitive_type=part.get("type"),
            ))

        # Spawn async 3D generation if Node is available
        if comfyui._node_available:
            output_path = os.path.join(_MODELS_DIR, f"{session_id}.glb")
            comfyui.create_job(session_id)
            asyncio.create_task(comfyui.generate_3d(session_id, upload_path, output_path))

            # If we got any bboxes, schedule mesh measurement to swap in once .glb is ready.
            if bboxes:
                parts_for_measure = [
                    {
                        "name": r.name,
                        "instructions": list(r.instructions),
                        "diameters": list(r.diameters),
                        "primitive_type": r.primitive_type,
                        "bbox": bboxes.get(r.name),
                    }
                    for r in results
                ]
                _measure_create(session_id)
                asyncio.create_task(_measure_after_mesh(session_id, parts_for_measure, output_path, grammar))

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Processing Error: {str(e)}")


@app.post("/feedback", status_code=201)
async def submit_feedback(feedback: FeedbackRequest, background_tasks: BackgroundTasks):
    if len(feedback.corrected_diameters) != len(feedback.original_diameters):
        raise HTTPException(
            status_code=422,
            detail="corrected_diameters must have the same length as original_diameters",
        )

    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available. Run the data pipeline setup first.")

    with get_db() as conn:
        insert_feedback(conn, feedback.model_dump())

    background_tasks.add_task(_maybe_trigger_retraining)
    return {"status": "ok"}


@app.get("/feedback/stats")
async def feedback_stats():
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database not available.")
    with get_db() as conn:
        return get_feedback_stats(conn)


@app.get("/")
async def root():
    return {"message": "AICrochet API is running. Access /static/index.html"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
