"""Dataset tooling: export, stats, and synthetic seeding."""

import json
import random
import logging
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.database import get_db, insert_training_record, get_training_records

logger = logging.getLogger(__name__)

PRIMITIVES = ["sphere", "cylinder", "cone", "frustum", "capsule", "teardrop", "flat_disc", "torus"]

# Base profiles at scale=1.0 (must stay in sync with geometry.py _build_profile)
_BASE_PROFILES = {
    "sphere":    [2, 4, 6, 8, 8, 8, 8, 6, 4, 2],
    "cylinder":  [4, 4, 4, 4, 4, 4],
    "cone":      [2, 4, 6, 8, 10],
    "frustum":   [4, 6, 8, 10, 10, 10, 10],
    "capsule":   [2, 4, 6, 8, 8, 8, 8, 8, 8, 6, 4, 2],
    "teardrop":  [2, 4, 6, 8, 8, 7, 5, 3, 2],
    "flat_disc": [2, 6, 10, 10],
    "torus":     [4, 6, 8, 6, 4],
}

import math
_SC_WIDTH = 1.0  # cm default


def _profile_to_stitch_counts(profile: list) -> list:
    return [max(6, 6 * round(((d * math.pi) / _SC_WIDTH) / 6)) for d in profile]


def seed_synthetic(scales: list = None):
    """Insert synthetic training records for all primitives at multiple scales."""
    scales = scales or [0.5, 1.0, 1.5, 2.0, 2.5]
    inserted = 0
    with get_db() as conn:
        for primitive in PRIMITIVES:
            base = _BASE_PROFILES[primitive]
            for scale in scales:
                profile = [d * scale for d in base]
                stitch_counts = _profile_to_stitch_counts(profile)
                record = {
                    "source_type": "synthetic",
                    "source_url": None,
                    "pattern_id": f"synthetic_{primitive}_{scale}",
                    "part_name": primitive,
                    "primitive_type": primitive,
                    "scale": scale,
                    "diameter_profile": profile,
                    "stitch_counts": stitch_counts,
                    "terminology": "US",
                    "quality_score": 0.6,  # synthetic records get moderate quality
                    "is_synthetic": True,
                }
                insert_training_record(conn, record)
                inserted += 1
    logger.info("Seeded %d synthetic records", inserted)
    return inserted


def export_split(
    split: str = "train",
    train_ratio: float = 0.8,
    min_quality: float = 0.5,
    output_path: str = None,
) -> list:
    """Export a stratified train or val split as a list of records.

    Stratification is per primitive_type. Records with quality < min_quality are excluded.
    """
    with get_db() as conn:
        all_records = get_training_records(conn, min_quality=min_quality)

    by_primitive = defaultdict(list)
    unclassified = []
    for rec in all_records:
        if rec.get("primitive_type"):
            by_primitive[rec["primitive_type"]].append(rec)
        else:
            unclassified.append(rec)

    result = []
    for ptype, records in by_primitive.items():
        random.shuffle(records)
        cut = int(len(records) * train_ratio)
        if split == "train":
            result.extend(records[:cut])
        else:
            result.extend(records[cut:])

    # Include unclassified records in train only
    if split == "train":
        random.shuffle(unclassified)
        cut = int(len(unclassified) * train_ratio)
        result.extend(unclassified[:cut])

    if output_path:
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        logger.info("Exported %d records (%s split) to %s", len(result), split, output_path)

    return result


def print_stats():
    """Print dataset statistics to stdout."""
    with get_db() as conn:
        from data.database import get_training_records, get_feedback_records
        all_records = get_training_records(conn, min_quality=0.0)
        feedback = get_feedback_records(conn)

    if not all_records:
        print("No training records in database.")
        return

    by_primitive = defaultdict(int)
    synthetic_count = 0
    quality_sum = 0.0
    dates = []

    for rec in all_records:
        ptype = rec.get("primitive_type") or "unclassified"
        by_primitive[ptype] += 1
        if rec.get("is_synthetic"):
            synthetic_count += 1
        quality_sum += rec.get("quality_score", 0.0)
        if rec.get("created_at"):
            dates.append(rec["created_at"])

    total = len(all_records)
    mean_quality = quality_sum / total if total else 0.0
    date_range = f"{min(dates)} → {max(dates)}" if dates else "N/A"

    print(f"\n{'='*50}")
    print(f"  AICrochet Dataset Statistics")
    print(f"{'='*50}")
    print(f"  Total records:     {total}")
    print(f"  Synthetic:         {synthetic_count} ({100*synthetic_count/total:.0f}%)")
    print(f"  Real:              {total - synthetic_count}")
    print(f"  Mean quality:      {mean_quality:.2f}")
    print(f"  Date range:        {date_range}")
    print(f"  Feedback records:  {len(feedback)}")
    print(f"\n  By primitive type:")
    for ptype, count in sorted(by_primitive.items()):
        print(f"    {ptype:<15} {count}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="data.dataset")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("stats")
    exp = sub.add_parser("export")
    exp.add_argument("--split", choices=["train", "val"], default="train")
    exp.add_argument("--min-quality", type=float, default=0.5)
    exp.add_argument("--output", default=None)
    sub.add_parser("seed")

    args = parser.parse_args()
    if args.cmd == "stats":
        print_stats()
    elif args.cmd == "export":
        export_split(split=args.split, min_quality=args.min_quality, output_path=args.output)
    elif args.cmd == "seed":
        seed_synthetic()
    else:
        parser.print_help()
