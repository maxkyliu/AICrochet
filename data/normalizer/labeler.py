"""Primitive type labeling and scale inference for normalized crochet pattern records."""

import logging

logger = logging.getLogger(__name__)

# ── Noise filter ──────────────────────────────────────────────────────────────

_NOISE_BLOCKLIST = [
    "ABBREVIATION", "ABBREV",
    "NOTE", "MATERIAL", "SUPPLY", "GAUGE",
    "TERMINOLOGY", "SKILL", "INTRODUCTION",
    "TIP", "INSTRUCTION", "STITCH",
    "YOU WILL NEED", "PATTERN INCLUDE",
]


def is_noise_record(part_name: str) -> bool:
    """Return True if part_name matches a known non-body-part section header."""
    upper = (part_name or "").upper()
    return any(token in upper for token in _NOISE_BLOCKLIST)


# ── Scale inference ───────────────────────────────────────────────────────────

_SCALE_REFERENCE = 24.0   # max stitches for a "size 1.0" part at worsted gauge
_SCALE_FLOOR = 0.25


def infer_scale(stitch_counts: list) -> float | None:
    """Infer a scale value from stitch count magnitude."""
    if not stitch_counts:
        return None
    raw = max(stitch_counts) / _SCALE_REFERENCE
    return round(max(raw, _SCALE_FLOOR), 2)


# ── Name-based labeler ────────────────────────────────────────────────────────

# Priority order matters: first match wins.
_NAME_RULES = [
    (["TORUS", "RING", "COLLAR"],               "torus"),
    (["EAR", "WING", "FIN"],                    "flat_disc"),
    (["FOOT", "BOOT", "BASE"],                  "frustum"),
    (["TAIL", "BEAK", "HORN", "SPIKE"],         "cone"),
    (["LEG", "ARM", "LIMB", "NECK", "STALK"],   "cylinder"),
    (["HEAD", "SNOUT", "MUZZLE"],               "sphere"),
    (["BODY", "TORSO", "TRUNK"],                "capsule"),
]


def label_by_name(part_name: str) -> str | None:
    """Return primitive type by keyword matching against part_name, or None."""
    upper = (part_name or "").upper()
    for keywords, ptype in _NAME_RULES:
        if any(kw in upper for kw in keywords):
            return ptype
    return None


# ── Shape-heuristic labeler ───────────────────────────────────────────────────

def _compute_profile_stats(stitch_counts: list) -> dict:
    """Compute shape statistics from a stitch count sequence."""
    n = len(stitch_counts)
    if n < 2:
        return {
            "min_ratio": 0.0,
            "flat_fraction": 0.0,
            "rise_slope": 0.0,
            "fall_slope": 0.0,
            "symmetry_score": 0.0,
            "is_monotone_rise": False,
        }

    max_val = max(stitch_counts)
    min_val = min(stitch_counts)
    min_ratio = min_val / max_val if max_val > 0 else 0.0

    flat_threshold = max_val * 0.9
    flat_fraction = sum(1 for v in stitch_counts if v >= flat_threshold) / n

    is_monotone_rise = all(
        stitch_counts[i] <= stitch_counts[i + 1] for i in range(n - 1)
    )

    mid = n // 2
    first_half = stitch_counts[:mid]
    second_half = stitch_counts[mid:]

    def _mean_rise(seq):
        diffs = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        pos = [d for d in diffs if d > 0]
        return sum(pos) / len(pos) if pos else 0.0

    def _mean_fall(seq):
        diffs = [seq[i] - seq[i + 1] for i in range(len(seq) - 1)]
        neg = [d for d in diffs if d > 0]
        return sum(neg) / len(neg) if neg else 0.0

    rise_slope = _mean_rise(first_half)
    fall_slope = _mean_fall(second_half)

    denom = rise_slope + fall_slope + 1e-6
    symmetry_score = max(0.0, 1.0 - abs(rise_slope - fall_slope) / denom)

    return {
        "min_ratio": min_ratio,
        "flat_fraction": flat_fraction,
        "rise_slope": rise_slope,
        "fall_slope": fall_slope,
        "symmetry_score": symmetry_score,
        "is_monotone_rise": is_monotone_rise,
    }


def label_by_shape(stitch_counts: list) -> str | None:
    """Infer primitive type from stitch count curve shape. Returns None if sequence too short."""
    if len(stitch_counts) < 4:
        return None

    s = _compute_profile_stats(stitch_counts)
    max_val = max(stitch_counts)
    min_val = min(stitch_counts)

    # Uniform sequence (all values within 15% of max) → cylinder
    if (max_val - min_val) / (max_val + 1e-6) < 0.15:
        return "cylinder"

    # High minimum but varying profile → torus (doesn't close at ends)
    if s["min_ratio"] > 0.4:
        return "torus"

    # Flat top covering >60% of rounds → cylinder
    if s["flat_fraction"] > 0.6:
        return "cylinder"

    if s["is_monotone_rise"]:
        return "cone"

    # Peak skewed toward start → long tapering tail → teardrop (check before sphere/capsule)
    # Use center of the flat section (not first occurrence of max) to handle symmetric flat tops
    n = len(stitch_counts)
    flat_threshold = max(stitch_counts) * 0.9
    flat_indices = [i for i, v in enumerate(stitch_counts) if v >= flat_threshold]
    peak_center = (flat_indices[0] + flat_indices[-1]) // 2 if flat_indices else n // 2
    rise_len = peak_center
    fall_len = n - 1 - peak_center
    if rise_len > 0 and fall_len > rise_len * 1.5:
        return "teardrop"

    # Symmetric rise-fall with small flat section → sphere
    if s["symmetry_score"] > 0.8 and s["flat_fraction"] < 0.4:
        return "sphere"

    # Symmetric rise-fall with moderate flat section → capsule
    if s["symmetry_score"] > 0.8 and s["flat_fraction"] < 0.65:
        return "capsule"

    return None


# ── Orchestrator ──────────────────────────────────────────────────────────────

def label_primitive(part_name: str, stitch_counts: list) -> str | None:
    """Assign a primitive type: name rules first, shape heuristic as fallback."""
    result = label_by_name(part_name)
    if result is not None:
        return result
    return label_by_shape(stitch_counts)
