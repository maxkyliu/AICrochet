import json
import math
import logging
import os

logger = logging.getLogger(__name__)


def _interp(x: float, xs: list, ys: list) -> float:
    """Piecewise-linear interpolation over sorted xs (both ends clamped)."""
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]

_SUPPORTED = frozenset([
    "sphere", "cylinder", "cone", "frustum", "capsule", "teardrop", "flat_disc", "torus"
])


def _build_profile(shape_type: str, scale: float) -> list:
    """Build an amplitude-scaled diameter profile for a primitive type.

    Sphere, capsule, and teardrop extend flat rounds proportionally to sqrt(scale)
    so larger shapes are taller as well as wider.
    """
    if shape_type == "cylinder":
        return [4.0 * scale] * 6

    if shape_type == "cone":
        return [d * scale for d in [2, 4, 6, 8, 10]]

    if shape_type == "torus":
        return [d * scale for d in [4, 6, 8, 6, 4]]

    # Shapes with ramp → flat plateau → tail structure.
    # (ramp, flat_val, base_flat_rounds, tail, extends_flat_with_scale)
    configs = {
        "sphere":    ([2, 4, 6], 8,  3, [6, 4, 2],    True),
        "frustum":   ([4, 6, 8], 10, 3, [],             False),
        "capsule":   ([2, 4, 6], 8,  5, [6, 4, 2],     True),
        "teardrop":  ([2, 4, 6], 8,  2, [7, 5, 3, 2],  True),
        "flat_disc": ([2, 6],    10, 1, [],              False),
    }

    ramp, flat_val, base_flat, tail, extends = configs[shape_type]
    flat_count = max(base_flat, round(base_flat * math.sqrt(scale))) if extends else base_flat
    raw = ramp + [flat_val] * flat_count + tail
    return [d * scale for d in raw]


# Reference amplitude: a scale-1.0 part peaks at 24 stitches (the same
# reference data/normalizer/labeler.py uses to infer scale from patterns).
_SCALE_REFERENCE_STITCHES = 24.0
_MIN_PROFILE_ROUNDS = 4
_MAX_PROFILE_ROUNDS = 48


class GeometryEngine:
    _model_cache: dict = {}
    _market_profiles: dict = None

    def _load_market_profiles(self) -> dict:
        if GeometryEngine._market_profiles is None:
            path = os.path.join(
                os.path.dirname(__file__), "..", "data", "models", "market_profiles.json"
            )
            try:
                with open(path) as f:
                    GeometryEngine._market_profiles = json.load(f).get("profiles", {})
            except (OSError, ValueError):
                GeometryEngine._market_profiles = {}
        return GeometryEngine._market_profiles

    def _market_profile(self, shape_type: str, scale: float):
        """Sample the market-learned prototype curve for this primitive.

        Returns a diameter profile list, or None if no prototype exists.
        """
        proto = self._load_market_profiles().get(shape_type)
        if not proto:
            return None
        curve = proto["curve"]
        max_count = _SCALE_REFERENCE_STITCHES * scale
        n = round(proto["rounds_per_max"] * max_count)
        n = max(_MIN_PROFILE_ROUNDS, min(_MAX_PROFILE_ROUNDS, n))
        # Resample the unit curve at n rounds, then convert counts → diameters.
        grid = [i / (n - 1) for i in range(n)]
        u = [i / (len(curve) - 1) for i in range(len(curve))]
        counts = [_interp(g, u, curve) * max_count for g in grid]
        return [c / math.pi for c in counts]

    def get_reference_curve(self, shape_type: str) -> tuple:
        """Unit-amplitude reference profile for a primitive: the market
        prototype when available, else the normalized hardcoded profile.

        Returns (curve, rounds_per_max) where curve is a list of floats with
        max 1.0 and rounds_per_max converts a max stitch count to a round
        count (n_rounds ≈ rounds_per_max × max_stitches).
        """
        proto = self._load_market_profiles().get(shape_type)
        if proto:
            return list(proto["curve"]), float(proto["rounds_per_max"])
        base = _build_profile(shape_type if shape_type in _SUPPORTED else "cylinder", 1.0)
        counts = [d * math.pi for d in base]
        max_count = max(counts)
        return [c / max_count for c in counts], len(counts) / max_count

    def get_diameters_for_primitive(self, shape_type: str, scale: float = 1.0) -> list:
        if os.environ.get("USE_MARKET_PROFILES", "true").lower() == "true":
            profile = self._market_profile(shape_type, scale)
            if profile is not None:
                return profile
        if os.environ.get("USE_LEARNED_MODEL", "false").lower() == "true":
            profile = self._predict_from_model(shape_type, scale)
            if profile is not None:
                return profile
        return _build_profile(shape_type, scale)

    def _predict_from_model(self, shape_type: str, scale: float):
        """Load and query the trained per-primitive regressor. Returns None on any failure."""
        try:
            import joblib
            models_dir = os.path.join(os.path.dirname(__file__), "..", "data", "models")
            model_path = os.path.join(models_dir, f"{shape_type}_regressor.joblib")
            if not os.path.exists(model_path):
                logger.warning(
                    "USE_LEARNED_MODEL=true but no model found at %s; using hardcoded profile",
                    model_path,
                )
                return None
            if shape_type not in self._model_cache:
                self._model_cache[shape_type] = joblib.load(model_path)
            model = self._model_cache[shape_type]

            # Build the same 7-feature vector used during training.
            # Approximate stitch counts from the base profile (diameter * π ≈ circumference).
            base = _build_profile(shape_type, 1.0)
            counts = [max(1, round(d * math.pi)) for d in base]
            n = len(counts)
            max_val = max(counts)
            flat_fraction = sum(1 for v in counts if v >= max_val * 0.9) / n

            mid = n // 2
            first_half, second_half = counts[:mid], counts[mid:]

            def _mean_pos(seq):
                diffs = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
                pos = [d for d in diffs if d > 0]
                return sum(pos) / len(pos) if pos else 0.0

            def _mean_neg(seq):
                diffs = [seq[i] - seq[i + 1] for i in range(len(seq) - 1)]
                neg = [d for d in diffs if d > 0]
                return sum(neg) / len(neg) if neg else 0.0

            rise = _mean_pos(first_half)
            fall = _mean_neg(second_half)
            symmetry = max(0.0, 1.0 - abs(rise - fall) / (rise + fall + 1e-6))

            features = [scale, float(n), float(max_val), rise, fall, flat_fraction, symmetry]
            return list(model.predict([features])[0])
        except Exception as exc:
            logger.warning(
                "Learned model error for '%s': %s; using hardcoded profile", shape_type, exc
            )
            return None

    def process_dependency_graph(self, graph: list) -> list:
        parts = []
        for node in graph:
            shape_type = node.get("type", "cylinder")
            scale = float(node.get("scale", 1.0))

            if scale <= 0:
                raise ValueError(
                    f"scale must be > 0, got {scale} for part '{node.get('name')}'"
                )

            if shape_type not in _SUPPORTED:
                logger.warning(
                    "Unknown primitive '%s' for part '%s'; falling back to cylinder",
                    shape_type, node.get("name"),
                )
                shape_type = "cylinder"

            diameters = self.get_diameters_for_primitive(shape_type, scale)
            parts.append({
                "name": node["name"],
                "diameters": diameters,
                "scale": scale,
                "type": shape_type,
            })
        return parts
