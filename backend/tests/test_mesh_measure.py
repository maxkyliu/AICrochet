"""Tests for backend/mesh_measure.py.

Synthetic-mesh fixtures (icosphere via trimesh) — no .glb files needed.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import trimesh

import mesh_measure


def _sphere():
    return trimesh.creation.icosphere(subdivisions=3, radius=1.0)


# ─── measure_part ─────────────────────────────────────────────────────────────

class TestMeasurePart:
    def test_top_half_rises_monotonically(self):
        # Top half of image (y_min=0, y_max=0.5) = top half of sphere → small at top, max at equator.
        d = mesh_measure.measure_part(_sphere(), [0.2, 0.0, 0.8, 0.5])
        assert len(d) >= 3, f"expected at least 3 slices, got {d}"
        assert all(x > 0 for x in d)
        assert d[-1] > d[0], f"top→equator should widen, got {d}"
        # Roughly monotonic rising (allow 1 jitter)
        rises = sum(1 for i in range(1, len(d)) if d[i] >= d[i-1] - 0.01)
        assert rises >= len(d) - 1, f"expected near-monotonic rise, got {d}"

    def test_full_sphere_bell_curve(self):
        d = mesh_measure.measure_part(_sphere(), [0.0, 0.0, 1.0, 1.0])
        assert len(d) >= 6
        # Peak should be near the middle, not at the ends.
        peak_idx = d.index(max(d))
        assert len(d) // 4 <= peak_idx <= len(d) - len(d) // 4 - 1

    def test_returns_empty_on_degenerate_bbox(self):
        # bbox with y_max <= y_min
        assert mesh_measure.measure_part(_sphere(), [0.0, 0.5, 1.0, 0.5]) == []
        # bbox out-of-range (negative is treated as still a band, but band outside mesh → 0 hits)
        assert mesh_measure.measure_part(_sphere(), []) == []
        assert mesh_measure.measure_part(_sphere(), [0, 0, 0]) == []

    def test_does_not_raise_on_invalid_input(self):
        # None bbox → empty list, not exception
        assert mesh_measure.measure_part(_sphere(), None) == []


# ─── load_normalized_mesh ─────────────────────────────────────────────────────

class TestLoadNormalizedMesh:
    def test_centers_at_origin(self, tmp_path):
        # Create an offset, elongated mesh and verify it ends up centered + upright.
        m = trimesh.creation.cylinder(radius=1.0, height=4.0, sections=24)
        m.apply_translation([5.0, -3.0, 2.0])
        # Lay it on its side (rotate 90° around X) so PCA must re-align Y.
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        path = tmp_path / "cyl.glb"
        m.export(str(path))

        normalized = mesh_measure.load_normalized_mesh(str(path))
        verts = np.asarray(normalized.vertices, dtype=float)
        center = verts.mean(axis=0)
        assert np.allclose(center, 0.0, atol=1e-6)

        # Principal axis (largest variance) should be Y.
        cov = np.cov(verts.T)
        _, vecs = np.linalg.eigh(cov)
        principal = vecs[:, -1]
        # Dot with Y axis should be ~±1 (sign doesn't matter for PCA)
        assert abs(abs(np.dot(principal, [0, 1, 0])) - 1.0) < 1e-3


# ─── _is_reasonable ───────────────────────────────────────────────────────────

class TestIsReasonable:
    def test_smooth_bell_passes(self):
        assert mesh_measure._is_reasonable([1.0, 2.0, 3.0, 3.0, 2.0, 1.0], 6) is True

    def test_empty_fails(self):
        assert mesh_measure._is_reasonable([], 6) is False

    def test_zero_in_array_fails(self):
        assert mesh_measure._is_reasonable([1.0, 0.0, 2.0, 3.0], 4) is False

    def test_length_far_from_expected_fails(self):
        # Got 2 when expecting 10 → far too short
        assert mesh_measure._is_reasonable([1.0, 2.0], 10) is False

    def test_wildly_jagged_fails(self):
        # Many direction flips → noise, not a real profile.
        assert mesh_measure._is_reasonable([1.0, 5.0, 1.0, 5.0, 1.0, 5.0], 6) is False
