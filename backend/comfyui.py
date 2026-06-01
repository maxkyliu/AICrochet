import asyncio
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
COMFYUI_PORT = os.environ.get("COMFYUI_PORT", "8188")
COMFYUI_3D_STEPS = os.environ.get("COMFYUI_3D_STEPS", "20")
IMAGE_TO_3D_SCRIPT = os.path.expanduser(
    "~/projects/image-blaster/.claude/scripts/asset-pipeline/image-to-3d.mjs"
)

_process: subprocess.Popen | None = None
_node_available: bool = False
_jobs: dict[str, dict] = {}


# ─── ComfyUI health / lifecycle ──────────────────────────────────────────────

def is_running() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def check_node() -> str | None:
    """Return Node version string if ≥ 22, else None. Sets _node_available."""
    global _node_available
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            logger.warning("node --version failed — 3D preview disabled")
            _node_available = False
            return None
        version_str = result.stdout.strip()  # e.g. "v22.3.0"
        major = int(version_str.lstrip("v").split(".")[0])
        if major < 22:
            logger.warning(
                "Node.js %s found but ≥ 22 required — 3D preview disabled", version_str
            )
            _node_available = False
            return None
        logger.info("Node.js %s found — 3D preview enabled", version_str)
        _node_available = True
        return version_str
    except Exception as exc:
        logger.warning("Could not check Node.js: %s — 3D preview disabled", exc)
        _node_available = False
        return None


def start() -> None:
    global _process
    if is_running():
        logger.info("ComfyUI already running at %s — skipping launch", COMFYUI_URL)
        return

    comfyui_dir = Path.home() / "ComfyUI"
    python_bin = Path.home() / "comfyui-env" / "bin" / "python"

    if not python_bin.exists():
        logger.warning("ComfyUI venv not found at %s — skipping launch", python_bin)
        return
    if not comfyui_dir.exists():
        logger.warning("ComfyUI directory not found at %s — skipping launch", comfyui_dir)
        return

    try:
        _process = subprocess.Popen(
            [str(python_bin), "main.py", "--port", COMFYUI_PORT],
            cwd=str(comfyui_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Started ComfyUI (PID: %d) on port %s", _process.pid, COMFYUI_PORT)
    except Exception as exc:
        logger.error("Failed to start ComfyUI: %s", exc)


def stop() -> None:
    global _process
    if _process is None:
        return
    if _process.poll() is not None:
        _process = None
        return
    logger.info("Stopping ComfyUI (PID: %d)…", _process.pid)
    _process.terminate()
    try:
        _process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        logger.warning("ComfyUI did not exit within 10 s — killing")
        _process.kill()
    _process = None
    logger.info("ComfyUI stopped")


# ─── Job tracker ─────────────────────────────────────────────────────────────

def create_job(session_id: str) -> None:
    _jobs[session_id] = {"status": "pending", "glb_url": None, "error": None}


def update_job(session_id: str, **kwargs) -> None:
    if session_id in _jobs:
        _jobs[session_id].update(kwargs)


def get_job(session_id: str) -> dict | None:
    return _jobs.get(session_id)


# ─── Async 3D generation ──────────────────────────────────────────────────────

async def generate_3d(session_id: str, image_path: str, output_path: str) -> None:
    if not is_running():
        update_job(session_id, status="failed", error="ComfyUI unreachable")
        logger.warning("3D generation skipped — ComfyUI not reachable")
        return

    update_job(session_id, status="generating")
    logger.info("Starting 3D generation for session %s", session_id)

    try:
        proc = await asyncio.create_subprocess_exec(
            "node", IMAGE_TO_3D_SCRIPT,
            "--input", image_path,
            "--output", output_path,
            "--steps", COMFYUI_3D_STEPS,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await proc.communicate()

        if proc.returncode == 0 and Path(output_path).exists():
            glb_url = f"/models/{Path(output_path).name}"
            update_job(session_id, status="done", glb_url=glb_url)
            logger.info("3D generation complete for session %s → %s", session_id, glb_url)
        else:
            stderr_tail = stderr_bytes.decode(errors="replace")[-500:]
            update_job(session_id, status="failed", error=stderr_tail)
            logger.error(
                "3D generation failed for session %s (exit %d): %s",
                session_id, proc.returncode, stderr_tail
            )
    except Exception as exc:
        update_job(session_id, status="failed", error=str(exc))
        logger.error("3D generation error for session %s: %s", session_id, exc)
