"""Market-data prototype profiles: per-primitive canonical stitch-count curves.

Learned from cleaned real pattern records (not the GBR regressors, whose
7 features never see the image and whose labels came from mis-parsed data).
Each primitive gets a length- and amplitude-normalized median curve built
from real amigurumi parts. GeometryEngine samples the curve at generation
time: amplitude = 24 stitches × scale (the same reference the scale labeler
uses), round count = learned rounds-per-stitch ratio × amplitude.

Usage:
    python -m models.prototypes build
    python -m models.prototypes eval
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "models" / "market_profiles.json"

CURVE_POINTS = 16      # resampled positions per normalized curve
MIN_QUALITY = 0.7      # extraction confidence floor
MIN_ROUNDS = 4         # too-short profiles carry no shape signal
MAX_ROUNDS = 24        # longer parts are usually whole-pattern concatenations
MIN_SAMPLES = 4        # primitives with fewer records keep the hardcoded profile


def _resample(counts: list, n_points: int) -> np.ndarray:
    """Normalize a stitch-count curve to unit length and unit amplitude."""
    arr = np.asarray(counts, dtype=float)
    u = np.linspace(0.0, 1.0, len(arr))
    grid = np.linspace(0.0, 1.0, n_points)
    return np.interp(grid, u, arr / arr.max())


def _load_clean_records() -> list:
    from data.database import get_db, get_training_records
    with get_db() as conn:
        records = get_training_records(conn, min_quality=MIN_QUALITY)
    return [
        r for r in records
        if not r.get("is_synthetic")
        and r.get("primitive_type")
        and MIN_ROUNDS <= len(r.get("stitch_counts") or []) <= MAX_ROUNDS
    ]


def build() -> dict:
    """Build per-primitive prototype curves and write market_profiles.json."""
    records = _load_clean_records()
    by_type: dict = {}
    for r in records:
        by_type.setdefault(r["primitive_type"], []).append(r)

    profiles = {}
    for ptype, recs in sorted(by_type.items()):
        if len(recs) < MIN_SAMPLES:
            logger.info("Skipping '%s': only %d samples (< %d)", ptype, len(recs), MIN_SAMPLES)
            continue
        curves = np.stack([_resample(r["stitch_counts"], CURVE_POINTS) for r in recs])
        prototype = np.median(curves, axis=0)
        rounds_per_max = float(np.median(
            [len(r["stitch_counts"]) / max(r["stitch_counts"]) for r in recs]
        ))
        profiles[ptype] = {
            "curve": [round(float(v), 4) for v in prototype],
            "rounds_per_max": round(rounds_per_max, 4),
            "n_samples": len(recs),
        }
        logger.info("'%s': %d samples, rounds_per_max=%.3f", ptype, len(recs), rounds_per_max)

    out = {"built_at": datetime.now().isoformat(), "curve_points": CURVE_POINTS,
           "profiles": profiles}
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(out, indent=2))
    logger.info("Wrote %d prototypes to %s", len(profiles), PROFILE_PATH)
    return out


def _shape_mae(predicted: np.ndarray, actual: list) -> float:
    """MAE in stitches between a predicted curve (sampled at the actual
    length, scaled to the actual max) and the actual counts."""
    arr = np.asarray(actual, dtype=float)
    grid = np.linspace(0.0, 1.0, len(arr))
    proto_u = np.linspace(0.0, 1.0, len(predicted))
    pred = np.interp(grid, proto_u, predicted) * arr.max()
    return float(np.abs(pred - arr).mean())


def evaluate() -> dict:
    """Leave-one-out comparison: prototype curve vs hardcoded profile.

    Both are scored shape-only (amplitude pinned to the record's true max),
    since amplitude comes from the vision model's scale either way.
    """
    from backend.geometry import _build_profile

    records = _load_clean_records()
    by_type: dict = {}
    for r in records:
        by_type.setdefault(r["primitive_type"], []).append(r)

    report = {}
    for ptype, recs in sorted(by_type.items()):
        if len(recs) < MIN_SAMPLES:
            continue
        hard_counts = np.asarray(
            [d * np.pi for d in _build_profile(ptype, 1.0)], dtype=float
        )
        hard_curve = hard_counts / hard_counts.max()

        proto_maes, hard_maes = [], []
        curves = [_resample(r["stitch_counts"], CURVE_POINTS) for r in recs]
        for i, r in enumerate(recs):
            others = np.stack([c for j, c in enumerate(curves) if j != i])
            prototype = np.median(others, axis=0)
            proto_maes.append(_shape_mae(prototype, r["stitch_counts"]))
            hard_maes.append(_shape_mae(hard_curve, r["stitch_counts"]))

        report[ptype] = {
            "n": len(recs),
            "prototype_mae": round(float(np.mean(proto_maes)), 3),
            "hardcoded_mae": round(float(np.mean(hard_maes)), 3),
        }
    return report


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="models.prototypes")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("build", help="Build prototypes from the training DB")
    sub.add_parser("eval", help="Leave-one-out MAE: prototype vs hardcoded")
    args = parser.parse_args()

    if args.cmd == "build":
        build()
    elif args.cmd == "eval":
        print(json.dumps(evaluate(), indent=2))
    else:
        parser.print_help()
