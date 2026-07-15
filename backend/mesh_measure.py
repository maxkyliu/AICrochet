"""Derive per-part diameter profiles from the session .glb by vertical band slicing.

Used by the /generate flow: after the Hunyuan3D mesh is ready, each part's LLM
bounding box (normalized image coords, image-y down) is mapped to a vertical
band on the PCA-aligned mesh; the band is sliced at N horizontal planes; each
slice's max horizontal extent becomes a diameter value. The resulting array
replaces GeometryEngine's hardcoded profile for that part.

Phase-1 assumption: photo and mesh share approximate "upright" orientation. No
camera pose estimation. See design D1/D2 of the direct-mesh-accuracy change.
"""

import logging
import math
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Slices per mesh-unit of band height. Calibrated so a full-doll-height part
# (band ≈ entire mesh y-extent) receives ~10 slices for typical Hunyuan3D
# meshes. Tune against real meshes if patterns come out the wrong row count.
SLICE_DENSITY = 5.0
MIN_SLICES = 4


def load_normalized_mesh(glb_path: str):
    """Load the GLB and PCA-align so the dominant principal axis points to +Y.

    Centers at origin. Does NOT rescale — absolute dimensions are preserved
    so measured diameters retain physical meaning for the grammar.
    """
    import trimesh
    mesh = trimesh.load(glb_path, force="mesh")
    verts = np.asarray(mesh.vertices, dtype=float)
    if verts.shape[0] < 3:
        return mesh
    verts = verts - verts.mean(axis=0)
    cov = np.cov(verts.T)
    _, vecs = np.linalg.eigh(cov)
    principal = vecs[:, -1]
    y = np.array([0.0, 1.0, 0.0])
    axis = np.cross(principal, y)
    s = np.linalg.norm(axis)
    if s > 1e-9:
        axis /= s
        ang = float(np.arccos(np.clip(np.dot(principal, y), -1.0, 1.0)))
        K = np.array([[0, -axis[2], axis[1]],
                      [axis[2], 0, -axis[0]],
                      [-axis[1], axis[0], 0]])
        R = np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * (K @ K)
        verts = verts @ R.T
    mesh.vertices = verts
    return mesh


# Tolerance added to the bbox x-window, as a fraction of the mesh's x-extent.
X_WINDOW_MARGIN = 0.05

# Width-profile correlation below this in both orientations means we cannot
# trust the photo↔mesh band mapping; the coordinator keeps the initial parts.
MIN_ORIENTATION_CONFIDENCE = 0.3
_ORIENTATION_BANDS = 10


def _mesh_width_curve(verts: np.ndarray, n_bands: int) -> np.ndarray:
    """Max horizontal extent per vertical band, ordered top of mesh → bottom."""
    y = verts[:, 1]
    edges = np.linspace(y.max(), y.min(), n_bands + 1)
    widths = np.zeros(n_bands)
    for i in range(n_bands):
        band = verts[(y <= edges[i]) & (y >= edges[i + 1])]
        if band.shape[0] >= 2:
            x_extent = band[:, 0].max() - band[:, 0].min()
            z_extent = band[:, 2].max() - band[:, 2].min()
            widths[i] = max(x_extent, z_extent)
    return widths


def _bbox_width_curve(bboxes: List[List[float]], n_bands: int) -> np.ndarray:
    """Width per band predicted from the parts' image bboxes, top of image → bottom."""
    centers = np.linspace(0.0, 1.0, n_bands + 1)[:-1] + 0.5 / n_bands
    widths = np.zeros(n_bands)
    for bbox in bboxes:
        if not bbox or len(bbox) != 4:
            continue
        x_min, y_min, x_max, y_max = bbox
        w = x_max - x_min
        if w <= 0 or y_max <= y_min:
            continue
        covered = (centers >= y_min) & (centers <= y_max)
        widths[covered] = np.maximum(widths[covered], w)
    return widths


def _correlation(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() < 1e-9 or b.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def normalize_bboxes(bboxes: List[Optional[List[float]]]) -> List[Optional[List[float]]]:
    """Rescale image-space bboxes so their union spans 0..1 in x and y.

    The photo frame is larger than the subject, but the mesh spans exactly
    the subject — so bbox coords must be subject-relative before they are
    mapped onto mesh extents. Invalid entries pass through as None.
    """
    valid = [b for b in bboxes if b and len(b) >= 4 and b[2] > b[0] and b[3] > b[1]]
    if not valid:
        return [None] * len(bboxes)
    x0 = min(b[0] for b in valid)
    x1 = max(b[2] for b in valid)
    y0 = min(b[1] for b in valid)
    y1 = max(b[3] for b in valid)
    x_span = (x1 - x0) or 1.0
    y_span = (y1 - y0) or 1.0
    out = []
    for b in bboxes:
        if not b or len(b) < 4 or b[2] <= b[0] or b[3] <= b[1]:
            out.append(None)
            continue
        out.append([
            (b[0] - x0) / x_span,
            (b[1] - y0) / y_span,
            (b[2] - x0) / x_span,
            (b[3] - y0) / y_span,
        ])
    return out


def resolve_orientation(mesh, bboxes: List[List[float]]):
    """Disambiguate the PCA sign by matching width profiles.

    Correlates the mesh's width-per-height curve against the curve predicted
    from the photo's part bboxes; flips the mesh about y when the flipped
    orientation correlates better. Returns (mesh, confidence) where confidence
    is the winning correlation (0.0 when there is no usable signal).
    """
    if not bboxes:
        return mesh, 0.0
    verts = np.asarray(mesh.vertices, dtype=float)
    if verts.shape[0] < 3:
        return mesh, 0.0

    mesh_widths = _mesh_width_curve(verts, _ORIENTATION_BANDS)
    predicted = _bbox_width_curve(bboxes, _ORIENTATION_BANDS)

    corr_normal = _correlation(mesh_widths, predicted)
    corr_flipped = _correlation(mesh_widths[::-1], predicted)

    if corr_flipped > corr_normal:
        verts = verts.copy()
        verts[:, 1] = -verts[:, 1]
        mesh.vertices = verts
    return mesh, max(corr_normal, corr_flipped)


def measure_part(mesh, bbox: List[float], n_slices: Optional[int] = None) -> List[float]:
    """Slice the mesh inside the part's vertical band and return diameter values.

    bbox: [x_min, y_min, x_max, y_max] in normalized image coords (image-y down).
    Each cross-section is restricted to vertices inside the bbox's x-window
    (mapped onto the mesh x-extent, with a small margin) so geometry from
    neighboring parts at the same height — arms beside a body, ears beside a
    head — does not inflate the measurement. The z-extent stays unconstrained:
    the photo carries no depth information.
    Returns [] on any failure (no slices, degenerate band, etc.) — never raises.
    """
    try:
        if not bbox or len(bbox) != 4:
            return []
        x_min_img, y_min_img, x_max_img, y_max_img = bbox
        if y_max_img <= y_min_img or x_max_img <= x_min_img:
            return []

        verts = np.asarray(mesh.vertices, dtype=float)
        mesh_y_min, mesh_y_max = float(verts[:, 1].min()), float(verts[:, 1].max())
        mesh_span = mesh_y_max - mesh_y_min
        if mesh_span <= 0:
            return []

        # Image-y points down; mesh-y points up. Flip when mapping.
        band_top    = mesh_y_max - y_min_img * mesh_span   # top of part = small image-y = large mesh-y
        band_bottom = mesh_y_max - y_max_img * mesh_span
        band_height = band_top - band_bottom
        if band_height <= 0:
            return []

        # Image-x maps linearly onto the mesh x-extent (no pose estimation;
        # mirror ambiguity accepted as a Phase-1 trade-off).
        mesh_x_min, mesh_x_max = float(verts[:, 0].min()), float(verts[:, 0].max())
        mesh_x_span = mesh_x_max - mesh_x_min
        margin = X_WINDOW_MARGIN * mesh_x_span
        win_lo = mesh_x_min + x_min_img * mesh_x_span - margin
        win_hi = mesh_x_min + x_max_img * mesh_x_span + margin

        if n_slices is None:
            n_slices = max(MIN_SLICES, round(band_height * SLICE_DENSITY))

        # Sample heights from top of band to bottom (matching natural crochet
        # round order from start of part to end).
        heights = np.linspace(band_top, band_bottom, n_slices)
        diameters = []
        for h in heights:
            section = mesh.section(plane_origin=[0, h, 0], plane_normal=[0, 1, 0])
            if section is None:
                continue
            section_verts = np.asarray(section.vertices, dtype=float)
            if section_verts.shape[0] < 2:
                continue
            in_window = section_verts[
                (section_verts[:, 0] >= win_lo) & (section_verts[:, 0] <= win_hi)
            ]
            if in_window.shape[0] < 2:
                continue
            x_extent = float(in_window[:, 0].max() - in_window[:, 0].min())
            z_extent = float(in_window[:, 2].max() - in_window[:, 2].min())
            diameter = max(x_extent, z_extent)
            if diameter > 0:
                diameters.append(diameter)
        return diameters
    except Exception as exc:
        logger.warning("measure_part failed: %s", exc)
        return []


# A measured curve flipping direction on more than this fraction of rounds is
# noise, not an amigurumi profile; its shape is not trusted.
MAX_FLIP_FRACTION = 0.3

# Swap quality gate: unit-amplitude MAE between the regularized profile and
# the reference shape above this keeps the initial-estimate part.
MAX_GATE_MAE = 0.25

# Round-count clamp for regularized profiles (kept in sync with geometry.py).
MIN_PROFILE_ROUNDS = 4
MAX_PROFILE_ROUNDS = 48


def _resample(values: List[float], n: int) -> np.ndarray:
    src = np.asarray(values, dtype=float)
    if len(src) == 1:
        return np.full(n, src[0])
    return np.interp(np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, len(src)), src)


def regularize_profile(
    calibrated: List[float],
    reference_curve: List[float],
    rounds_per_max: float,
    stitch_width: float,
    alpha: float,
) -> tuple:
    """Blend a calibrated measured curve with the primitive's reference shape.

    The mesh contributes amplitude and (when smooth enough) coarse shape; the
    reference curve constrains the profile to a crochetable curve. Round count
    derives from the calibrated amplitude via rounds_per_max, not slice count.

    Returns (diameter_profile, mae) where mae is the unit-amplitude mean
    absolute error of the blended shape against the reference shape. Returns
    ([], inf) on degenerate input.
    """
    if not calibrated or max(calibrated) <= 0 or not reference_curve:
        return [], float("inf")
    amplitude = max(calibrated)
    max_stitches = amplitude * math.pi / stitch_width
    n = round(rounds_per_max * max_stitches)
    n = max(MIN_PROFILE_ROUNDS, min(MAX_PROFILE_ROUNDS, n))

    measured_unit = _resample([d / amplitude for d in calibrated], n)
    reference_unit = _resample(reference_curve, n)

    if _flip_fraction(calibrated) > MAX_FLIP_FRACTION:
        alpha = 0.0  # shape untrusted: reference shape, measured amplitude
    blend_unit = alpha * measured_unit + (1.0 - alpha) * reference_unit

    mae = float(np.abs(blend_unit - reference_unit).mean())
    return [float(v * amplitude) for v in blend_unit], mae


def _flip_fraction(diameters: List[float]) -> float:
    """Fraction of rounds where the profile reverses direction."""
    if len(diameters) < 4:
        return 0.0
    flips = 0
    for i in range(2, len(diameters)):
        d_prev = diameters[i - 1] - diameters[i - 2]
        d_now = diameters[i] - diameters[i - 1]
        if d_prev * d_now < 0:
            flips += 1
    return flips / len(diameters)


def _is_reasonable(diameters: List[float], expected_n: int) -> bool:
    """Sanity-check a measured diameter array against the initial profile's
    round count. Reject obviously bad results so the coordinator can fall
    back to the initial-estimate part."""
    if not diameters:
        return False
    if any(d <= 0 for d in diameters):
        return False
    # Length drift vs the expected round count: tolerate ±50%
    if expected_n > 0 and (
        len(diameters) < expected_n * 0.5 or len(diameters) > expected_n * 1.5
    ):
        return False
    return True
