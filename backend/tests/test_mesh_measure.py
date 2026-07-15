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


class TestXWindowMasking:
    def test_neighbor_geometry_outside_window_excluded(self):
        # Body sphere at origin plus an "arm" sphere offset in +x at the same
        # height. Body bbox covers only the left ~60% of the image.
        body = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        arm = trimesh.creation.icosphere(subdivisions=3, radius=0.4)
        arm.apply_translation([1.8, 0.0, 0.0])
        combined = trimesh.util.concatenate([body, arm])

        # Combined mesh x-extent: -1.0 .. 2.2. Body occupies image-x ≈ 0 .. 0.62.
        with_arm = mesh_measure.measure_part(combined, [0.0, 0.0, 0.60, 1.0])
        body_only = mesh_measure.measure_part(body, [0.0, 0.0, 1.0, 1.0])
        assert with_arm, "expected slices from the body band"
        # Without masking the equator diameter would span body+arm (~3.2);
        # with masking it stays near the body's own diameter (~2.0).
        assert max(with_arm) < max(body_only) * 1.15

    def test_degenerate_x_window_returns_empty(self):
        assert mesh_measure.measure_part(_sphere(), [0.5, 0.0, 0.5, 1.0]) == []


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


# ─── normalize_bboxes ─────────────────────────────────────────────────────────

class TestNormalizeBboxes:
    def test_union_rescaled_to_unit_range(self):
        # Subject occupies x 0.2..0.8, y 0.1..0.9 of the photo frame.
        head = [0.4, 0.1, 0.6, 0.4]
        body = [0.2, 0.4, 0.8, 0.9]
        n_head, n_body = mesh_measure.normalize_bboxes([head, body])
        assert n_head[1] == 0.0                      # union top → 0
        assert n_body[3] == 1.0                      # union bottom → 1
        assert n_body[0] == 0.0 and n_body[2] == 1.0
        # Head keeps its relative width within the subject.
        assert 0.0 < n_head[0] < n_head[2] < 1.0

    def test_invalid_entries_pass_through_as_none(self):
        out = mesh_measure.normalize_bboxes([None, [0.5, 0.2, 0.5, 0.8], [0.2, 0.2, 0.8, 0.8]])
        assert out[0] is None
        assert out[1] is None
        assert out[2] == [0.0, 0.0, 1.0, 1.0]

    def test_all_invalid_returns_nones(self):
        assert mesh_measure.normalize_bboxes([None, []]) == [None, None]


# ─── resolve_orientation ──────────────────────────────────────────────────────

class TestResolveOrientation:
    def _snowman(self):
        """Small head on top (+y), big body below — distinct width profile."""
        head = trimesh.creation.icosphere(subdivisions=2, radius=0.5)
        head.apply_translation([0.0, 1.5, 0.0])
        body = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        return trimesh.util.concatenate([head, body])

    # bboxes matching the snowman photo: head high (small), body low (wide)
    _BBOXES = [
        [0.35, 0.05, 0.65, 0.35],   # head: top of image, narrow
        [0.15, 0.35, 0.85, 0.95],   # body: bottom of image, wide
    ]

    def test_correct_orientation_kept_with_confidence(self):
        mesh = self._snowman()
        top_y_before = float(np.asarray(mesh.vertices)[:, 1].max())
        mesh, conf = mesh_measure.resolve_orientation(mesh, self._BBOXES)
        assert conf > mesh_measure.MIN_ORIENTATION_CONFIDENCE
        assert float(np.asarray(mesh.vertices)[:, 1].max()) == top_y_before

    def test_inverted_mesh_gets_flipped(self):
        mesh = self._snowman()
        verts = np.asarray(mesh.vertices, dtype=float).copy()
        verts[:, 1] = -verts[:, 1]          # head now at the bottom
        mesh.vertices = verts
        mesh, conf = mesh_measure.resolve_orientation(mesh, self._BBOXES)
        assert conf > mesh_measure.MIN_ORIENTATION_CONFIDENCE
        # After the fix the head is back on top: the mesh extends further
        # above the body's equator than below it (head top ≈ +2.0, body
        # bottom ≈ −1.0).
        fixed_y = np.asarray(mesh.vertices, dtype=float)[:, 1]
        assert fixed_y.max() > abs(fixed_y.min())

    def test_no_bboxes_returns_zero_confidence(self):
        mesh, conf = mesh_measure.resolve_orientation(self._snowman(), [])
        assert conf == 0.0

    def test_uniform_mesh_returns_low_confidence(self):
        # A cylinder has a flat width profile → no orientation signal.
        cyl = trimesh.creation.cylinder(radius=1.0, height=4.0, sections=24)
        _, conf = mesh_measure.resolve_orientation(cyl, self._BBOXES)
        assert conf <= mesh_measure.MIN_ORIENTATION_CONFIDENCE


# ─── regularize_profile ───────────────────────────────────────────────────────

_REF_CURVE = [0.25, 0.5, 0.75, 1.0, 1.0, 0.75, 0.5, 0.25]


class TestRegularizeProfile:
    def test_noisy_shape_falls_back_to_reference_at_measured_amplitude(self):
        jagged = [2.0, 8.0, 2.0, 8.0, 2.0, 8.0]      # flip fraction 0.67
        profile, mae = mesh_measure.regularize_profile(
            jagged, _REF_CURVE, rounds_per_max=0.4, stitch_width=1.0, alpha=0.5
        )
        assert mae == 0.0                             # α forced to 0 → pure reference shape
        assert max(profile) == 8.0                    # measured amplitude preserved

    def test_smooth_shape_blends_toward_measurement(self):
        # Smooth but flat curve, unlike the bell reference.
        flat = [6.0, 6.0, 6.0, 6.0, 6.0, 6.0]
        profile, mae = mesh_measure.regularize_profile(
            flat, _REF_CURVE, rounds_per_max=0.4, stitch_width=1.0, alpha=0.5
        )
        assert mae > 0.0
        assert max(profile) <= 6.0

    def test_round_count_follows_amplitude_not_slice_count(self):
        import math
        # Amplitude → 36 stitches; rounds_per_max 0.4 → 14 rounds, from 5 slices.
        amplitude = 36.0 / math.pi
        smooth = [amplitude * v for v in [0.3, 0.7, 1.0, 0.7, 0.3]]
        profile, _ = mesh_measure.regularize_profile(
            smooth, _REF_CURVE, rounds_per_max=0.4, stitch_width=1.0, alpha=0.5
        )
        assert len(profile) == 14

    def test_degenerate_input_returns_empty(self):
        assert mesh_measure.regularize_profile([], _REF_CURVE, 0.4, 1.0, 0.5) == ([], float("inf"))
        assert mesh_measure.regularize_profile([0.0], _REF_CURVE, 0.4, 1.0, 0.5)[0] == []


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

    def test_jagged_passes_sanity_but_flags_high_flip_fraction(self):
        # Jagged curves are no longer rejected outright — their amplitude is
        # still usable. The flip fraction flags them so the blend drops shape.
        jagged = [1.0, 5.0, 1.0, 5.0, 1.0, 5.0]
        assert mesh_measure._is_reasonable(jagged, 6) is True
        assert mesh_measure._flip_fraction(jagged) > mesh_measure.MAX_FLIP_FRACTION

    def test_smooth_curve_has_low_flip_fraction(self):
        smooth = [1.0, 2.0, 3.0, 3.0, 2.0, 1.0]
        assert mesh_measure._flip_fraction(smooth) <= mesh_measure.MAX_FLIP_FRACTION
