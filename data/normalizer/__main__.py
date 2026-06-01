"""CLI: python -m data.normalizer run [--source ravelry|amigurumitoday]"""

import argparse
import json
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def main():
    parser = argparse.ArgumentParser(prog="data.normalizer")
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Normalize scraped raw records and write to DB")
    run_p.add_argument(
        "--source",
        choices=["ravelry", "amigurumitoday", "all"],
        default="all",
        help="Which raw data source to process",
    )
    run_p.add_argument(
        "--relabel",
        action="store_true",
        help="Re-apply primitive labeler to existing unlabeled DB records (no new normalization)",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cmd == "run":
        from data.normalizer.normalizer import normalize_pattern
        from data.database import get_db, insert_training_record

        if args.relabel:
            from data.database import get_unlabeled_records, update_training_record_label
            from data.normalizer.labeler import label_primitive, infer_scale
            updated = 0
            with get_db() as conn:
                unlabeled = get_unlabeled_records(conn)
                for rec in unlabeled:
                    ptype = label_primitive(rec["part_name"], rec["stitch_counts"])
                    scale = infer_scale(rec["stitch_counts"])
                    if ptype is not None:
                        update_training_record_label(conn, rec["id"], ptype, scale)
                        updated += 1
            logging.info("Relabeled %d previously unlabeled records", updated)
            return

        raw_base = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
        sources = []

        if args.source in ("ravelry", "all"):
            sources.append(("ravelry", raw_base / "ravelry"))
        if args.source in ("amigurumitoday", "all"):
            sources.append(("wordpress", raw_base / "1dogwoof"))

        total_written = 0
        with get_db() as conn:
            for source_name, raw_dir in sources:
                if not raw_dir.exists():
                    logging.warning("Raw dir not found: %s", raw_dir)
                    continue
                for json_file in raw_dir.glob("*.json"):
                    try:
                        raw = json.loads(json_file.read_text())
                        raw.setdefault("source_type", source_name)
                        records = normalize_pattern(raw)
                        for rec in records:
                            insert_training_record(conn, rec)
                            total_written += 1
                    except Exception as exc:
                        logging.warning("Failed to normalize %s: %s", json_file.name, exc)

        logging.info("Wrote %d training records to database", total_written)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
