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


def measure_part(mesh, bbox: List[float], n_slices: Optional[int] = None) -> List[float]:
    """Slice the mesh inside the part's vertical band and return diameter values.

    bbox: [x_min, y_min, x_max, y_max] in normalized image coords (image-y down).
    Returns [] on any failure (no slices, degenerate band, etc.) — never raises.
    """
    try:
        if not bbox or len(bbox) != 4:
            return []
        _, y_min_img, _, y_max_img = bbox
        if y_max_img <= y_min_img:
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

        if n_slices is None:
            n_slices = max(MIN_SLICES, round(band_height * SLICE_DENSITY))

        # Sample heights from top of band to bottom (matching natural crochet
        # round order from start of part to end).
        heights = np.linspace(band_top, band_bottom, n_slices)
        import trimesh
        diameters = []
        for h in heights:
            section = mesh.section(plane_origin=[0, h, 0], plane_normal=[0, 1, 0])
            if section is None:
                continue
            section_verts = np.asarray(section.vertices, dtype=float)
            if section_verts.shape[0] < 2:
                continue
            x_extent = float(section_verts[:, 0].max() - section_verts[:, 0].min())
            z_extent = float(section_verts[:, 2].max() - section_verts[:, 2].min())
            diameter = max(x_extent, z_extent)
            if diameter > 0:
                diameters.append(diameter)
        return diameters
    except Exception as exc:
        logger.warning("measure_part failed: %s", exc)
        return []


def _is_reasonable(diameters: List[float], expected_n: int) -> bool:
    """Sanity-check a measured diameter array. Reject obviously bad results so
    the coordinator can fall back to the hardcoded GeometryEngine profile."""
    if not diameters:
        return False
    if any(d <= 0 for d in diameters):
        return False
    # Length drift: tolerate ±50%
    if expected_n > 0 and (
        len(diameters) < expected_n * 0.5 or len(diameters) > expected_n * 1.5
    ):
        return False
    # Wildly non-monotonic: count direction changes; more than half the rounds
    # flipping direction means noise, not a smooth amigurumi profile.
    if len(diameters) >= 4:
        flips = 0
        for i in range(2, len(diameters)):
            d_prev = diameters[i - 1] - diameters[i - 2]
            d_now = diameters[i] - diameters[i - 1]
            if d_prev * d_now < 0:
                flips += 1
        if flips > len(diameters) * 0.5:
            return False
    return True
