"""Ravelry API scraper for amigurumi patterns.

Requires RAVELRY_USERNAME and RAVELRY_API_KEY env vars (personal API key auth).
Respects 1 req/sec rate limit with exponential backoff on 429.
Stores raw JSON to data/raw/ravelry/<pattern_id>.json and maintains a cursor
for resumable pagination.
"""

import os
import json
import time
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

RAW_DIR = Path(os.path.dirname(__file__), "..", "..", "data", "raw", "ravelry").resolve()
CURSOR_FILE = RAW_DIR / "cursor.json"
REVIEW_LOG = Path(os.path.dirname(__file__), "..", "..", "data", "raw", "review_log.jsonl").resolve()

API_BASE = "https://api.ravelry.com"
PAGE_SIZE = 100
MIN_DELAY = 1.0  # seconds between requests


class RavelryClient:
    def __init__(self):
        username = os.environ.get("RAVELRY_USERNAME")
        api_key = os.environ.get("RAVELRY_API_KEY")
        if not username or not api_key:
            raise RuntimeError(
                "Set RAVELRY_USERNAME and RAVELRY_API_KEY environment variables."
            )
        self.auth = (username, api_key)
        self._last_request = 0.0

    def _get(self, path: str, params: dict = None) -> dict:
        elapsed = time.time() - self._last_request
        if elapsed < MIN_DELAY:
            time.sleep(MIN_DELAY - elapsed)

        backoff = 2.0
        for attempt in range(6):
            resp = requests.get(f"{API_BASE}{path}", params=params, auth=self.auth, timeout=30)
            self._last_request = time.time()
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = backoff * (2 ** attempt)
                wait = min(wait, 60.0)
                logger.warning("Rate limited (429); waiting %.1fs", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()

        raise RuntimeError("Max retries exceeded on Ravelry API")

    def search_amigurumi(self, page: int = 1) -> dict:
        return self._get("/patterns/search.json", params={
            "craft": "crochet",
            "pattern-type": "amigurumi",
            "page": page,
            "page_size": PAGE_SIZE,
            "sort": "recently-popular",
        })

    def get_pattern(self, pattern_id: int) -> dict:
        return self._get(f"/patterns/{pattern_id}.json")


def _load_cursor() -> dict:
    if CURSOR_FILE.exists():
        return json.loads(CURSOR_FILE.read_text())
    return {"page": 1, "seen_ids": []}


def _save_cursor(cursor: dict) -> None:
    CURSOR_FILE.write_text(json.dumps(cursor))


def _seen_ids() -> set:
    seen = set()
    for f in RAW_DIR.glob("*.json"):
        if f.name == "cursor.json":
            continue
        seen.add(f.stem)
    return seen


def _log_rejected_photo(url: str, reason: str) -> None:
    REVIEW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_LOG, "a") as f:
        f.write(json.dumps({"url": url, "reason": reason}) + "\n")


def run(limit: int = None, photo_classifier=None):
    """Main scrape loop. Downloads patterns and optionally filters photos.

    photo_classifier: callable(image_url) -> (class, confidence) or None to skip filtering.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = RavelryClient()
    cursor = _load_cursor()
    seen = _seen_ids()

    collected = 0
    page = cursor["page"]

    while True:
        logger.info("Fetching page %d", page)
        result = client.search_amigurumi(page=page)
        patterns = result.get("patterns", [])

        if not patterns:
            logger.info("No more patterns; scrape complete.")
            break

        for p in patterns:
            pid = str(p["id"])
            if pid in seen:
                logger.debug("Skipping already-seen pattern %s", pid)
                continue

            # Fetch full pattern detail
            try:
                detail = client.get_pattern(p["id"])
            except Exception as exc:
                logger.warning("Failed to fetch pattern %s: %s", pid, exc)
                continue

            pattern_data = detail.get("pattern", detail)

            # Filter photos through classifier if provided
            photos = pattern_data.get("photos", [])
            accepted_photos = []
            for photo in photos:
                url = photo.get("medium_url") or photo.get("small_url", "")
                if photo_classifier and url:
                    try:
                        cls, conf = photo_classifier(url)
                        if cls == "finished" and conf >= 0.85:
                            accepted_photos.append(url)
                        else:
                            _log_rejected_photo(url, f"class={cls} conf={conf:.2f}")
                    except Exception as exc:
                        _log_rejected_photo(url, f"classifier_error: {exc}")
                else:
                    accepted_photos.append(url)

            pattern_data["accepted_photo_urls"] = accepted_photos

            out_path = RAW_DIR / f"{pid}.json"
            out_path.write_text(json.dumps(pattern_data, indent=2))
            seen.add(pid)
            collected += 1
            logger.info("Stored pattern %s (%d total)", pid, collected)

            if limit and collected >= limit:
                _save_cursor({"page": page})
                logger.info("Limit %d reached; stopping.", limit)
                return

        page += 1
        cursor["page"] = page
        _save_cursor(cursor)
