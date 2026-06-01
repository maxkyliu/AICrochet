import math
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from geometry import GeometryEngine, _build_profile

geo = GeometryEngine()

ALL_PRIMITIVES = ["sphere", "cylinder", "cone", "frustum", "capsule", "teardrop", "flat_disc", "torus"]


# --- Amplitude scaling ---

class TestAmplitudeScaling:
    def test_sphere_scale1_unchanged(self):
        d = geo.get_diameters_for_primitive("sphere", 1.0)
        assert max(d) == pytest.approx(8.0)

    def test_sphere_scale_multiplies_amplitude(self):
        d1 = geo.get_diameters_for_primitive("sphere", 1.0)
        d2 = geo.get_diameters_for_primitive("sphere", 2.5)
        for v1, v2 in zip(d1, d1):  # same length portion
            pass
        assert max(d2) == pytest.approx(max(d1) * 2.5)

    @pytest.mark.parametrize("primitive", ALL_PRIMITIVES)
    def test_scale_doubles_max_diameter(self, primitive):
        d1 = geo.get_diameters_for_primitive(primitive, 1.0)
        d2 = geo.get_diameters_for_primitive(primitive, 2.0)
        assert max(d2) == pytest.approx(max(d1) * 2.0)

    @pytest.mark.parametrize("primitive", ALL_PRIMITIVES)
    def test_all_diameters_positive(self, primitive):
        d = geo.get_diameters_for_primitive(primitive, 1.0)
        assert all(v > 0 for v in d)


# --- Flat-round extension for sphere ---

class TestFlatRoundExtension:
    def test_sphere_scale1_has_3_flat_rounds(self):
        d = _build_profile("sphere", 1.0)
        flat_val = max(d)
        flat_rounds = sum(1 for v in d if v == flat_val)
        assert flat_rounds == 3

    def test_sphere_scale4_has_at_least_5_flat_rounds(self):
        d = _build_profile("sphere", 4.0)
        flat_val = max(d)
        flat_rounds = sum(1 for v in d if v == flat_val)
        assert flat_rounds >= 5

    def test_teardrop_extends_flat_with_scale(self):
        d1 = _build_profile("teardrop", 1.0)
        d4 = _build_profile("teardrop", 4.0)
        assert len(d4) > len(d1)

    def test_cylinder_does_not_extend_with_scale(self):
        d1 = _build_profile("cylinder", 1.0)
        d4 = _build_profile("cylinder", 4.0)
        assert len(d4) == len(d1)


# --- Shape correctness ---

class TestShapeProfiles:
    def test_sphere_symmetric(self):
        d = _build_profile("sphere", 1.0)
        assert d[0] == d[-1]
        assert d[1] == d[-2]

    def test_cone_monotonically_increasing(self):
        d = _build_profile("cone", 1.0)
        for i in range(len(d) - 1):
            assert d[i] <= d[i + 1]

    def test_frustum_no_narrowing_at_end(self):
        d = _build_profile("frustum", 1.0)
        assert d[-1] == max(d)

    def test_flat_disc_very_short(self):
        d = _build_profile("flat_disc", 1.0)
        assert len(d) <= 5

    def test_torus_non_monotonic(self):
        d = _build_profile("torus", 1.0)
        assert d[0] < max(d) and d[-1] < max(d)

    def test_capsule_longer_flat_than_sphere(self):
        sphere = _build_profile("sphere", 1.0)
        capsule = _build_profile("capsule", 1.0)
        flat_val = max(sphere)
        sphere_flat = sum(1 for v in sphere if v == flat_val)
        capsule_flat = sum(1 for v in capsule if v == max(capsule))
        assert capsule_flat > sphere_flat


# --- Scale validation ---

class TestValidation:
    def test_zero_scale_raises(self):
        with pytest.raises(ValueError, match="scale must be > 0"):
            geo.process_dependency_graph([{"name": "Head", "type": "sphere", "scale": 0}])

    def test_negative_scale_raises(self):
        with pytest.raises(ValueError, match="scale must be > 0"):
            geo.process_dependency_graph([{"name": "Head", "type": "sphere", "scale": -1.0}])

    def test_unknown_type_falls_back_to_cylinder(self):
        parts = geo.process_dependency_graph([{"name": "Blob", "type": "gloop", "scale": 1.0}])
        cylinder_d = geo.get_diameters_for_primitive("cylinder", 1.0)
        assert parts[0]["diameters"] == cylinder_d


# --- process_dependency_graph output ---

class TestDependencyGraph:
    def test_scale_preserved_in_output(self):
        parts = geo.process_dependency_graph([{"name": "Body", "type": "sphere", "scale": 1.8}])
        assert parts[0]["scale"] == 1.8

    def test_type_preserved_in_output(self):
        parts = geo.process_dependency_graph([{"name": "Head", "type": "capsule", "scale": 1.0}])
        assert parts[0]["type"] == "capsule"

    def test_multiple_parts_processed(self):
        graph = [
            {"name": "Head", "type": "sphere", "scale": 1.0},
            {"name": "Body", "type": "cylinder", "scale": 1.5},
        ]
        parts = geo.process_dependency_graph(graph)
        assert len(parts) == 2
        assert parts[0]["name"] == "Head"
        assert parts[1]["name"] == "Body"
