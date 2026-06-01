"""CLI: python -m data.scraper run --source ravelry|amigurumitoday [--limit N]"""

import argparse
import logging
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def main():
    parser = argparse.ArgumentParser(prog="data.scraper")
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Run the scraper")
    run_p.add_argument(
        "--source",
        choices=["ravelry", "amigurumitoday"],
        required=True,
        help="Data source to scrape",
    )
    run_p.add_argument("--limit", type=int, default=None, help="Max patterns to collect")
    run_p.add_argument("--no-classifier", action="store_true", help="Skip photo classifier")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cmd == "run":
        if args.source == "ravelry":
            from data.scraper.ravelry import run
            classifier = None
            if not args.no_classifier:
                from data.scraper.photo_classifier import PhotoClassifier
                clf = PhotoClassifier()
                classifier = clf.predict
            run(limit=args.limit, photo_classifier=classifier)

        elif args.source == "amigurumitoday":
            from data.scraper.amigurumitoday import run
            run(limit=args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
