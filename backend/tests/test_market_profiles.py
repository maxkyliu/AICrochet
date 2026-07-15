import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from geometry import GeometryEngine

# A synthetic sphere-like prototype: rises to 1.0 mid-curve, falls back.
_FAKE_PROFILES = {
    "sphere": {
        "curve": [0.25, 0.5, 0.75, 1.0, 1.0, 0.75, 0.5, 0.25],
        "rounds_per_max": 0.4,
        "n_samples": 10,
    },
}


@pytest.fixture
def market_geo(monkeypatch):
    monkeypatch.setenv("USE_MARKET_PROFILES", "true")
    monkeypatch.setattr(GeometryEngine, "_market_profiles", dict(_FAKE_PROFILES))
    yield GeometryEngine()
    GeometryEngine._market_profiles = None


class TestMarketProfiles:
    def test_amplitude_follows_scale_reference(self, market_geo):
        # scale 1.0 → max count 24 → max diameter 24/π
        d = market_geo.get_diameters_for_primitive("sphere", 1.0)
        assert max(d) == pytest.approx(24.0 / math.pi, rel=1e-6)

    def test_round_count_scales_with_size(self, market_geo):
        small = market_geo.get_diameters_for_primitive("sphere", 1.0)
        large = market_geo.get_diameters_for_primitive("sphere", 2.0)
        assert len(large) > len(small)
        # rounds_per_max 0.4 × 24 stitches ≈ 10 rounds at scale 1.0
        assert len(small) == 10

    def test_curve_shape_preserved(self, market_geo):
        d = market_geo.get_diameters_for_primitive("sphere", 1.0)
        peak = d.index(max(d))
        assert 0 < peak < len(d) - 1          # peak is interior
        assert d[0] < d[peak] and d[-1] < d[peak]

    def test_missing_primitive_falls_back_to_hardcoded(self, market_geo):
        d = market_geo.get_diameters_for_primitive("cylinder", 1.0)
        assert d == [4.0] * 6                  # hardcoded cylinder profile

    def test_disabled_flag_uses_hardcoded(self, monkeypatch, market_geo):
        monkeypatch.setenv("USE_MARKET_PROFILES", "false")
        d = market_geo.get_diameters_for_primitive("sphere", 1.0)
        assert max(d) == pytest.approx(8.0)    # hardcoded sphere amplitude

    def test_reference_curve_from_prototype(self, market_geo):
        curve, rpm = market_geo.get_reference_curve("sphere")
        assert curve == _FAKE_PROFILES["sphere"]["curve"]
        assert rpm == 0.4

    def test_reference_curve_falls_back_to_normalized_hardcoded(self, market_geo):
        curve, rpm = market_geo.get_reference_curve("teardrop")
        assert max(curve) == pytest.approx(1.0)
        assert all(0 < v <= 1.0 for v in curve)
        assert rpm > 0

    def test_profiles_compile_through_grammar(self, market_geo):
        from grammar import CrochetGrammar
        d = market_geo.get_diameters_for_primitive("sphere", 1.5)
        instructions = CrochetGrammar().compile_part("Head", d, "sphere")
        rounds = [l for l in instructions if l.startswith("Rnd ")]
        assert len(rounds) >= 4
        assert rounds[0].endswith("[6]")
