"""Free amigurumi pattern scraper using WordPress REST APIs.

amigurumitoday.com is defunct (redirects to atom.com as of 2026).
This module targets WordPress-based pattern blogs that expose the WP REST API,
returning clean JSON without JavaScript rendering.

Sources:
  - 1dogwoof.com  — categories: crochet-toys (378), crochet-free-patterns (370)

Adding more sources: define a new entry in SOURCES and it will be scraped automatically.
Each source entry:
  base_url        Root of the WordPress site
  categories      List of WP category IDs to include (AND-filtered by WP)
  search          Optional keyword filter passed to ?search=
  label           Short name used in source_type field and raw output dir
"""

import json
import logging
import time
import urllib.request
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Install beautifulsoup4: pip install beautifulsoup4")

SOURCES = [
    {
        "label": "1dogwoof",
        "base_url": "https://www.1dogwoof.com",
        "categories": [378],        # crochet-toys (97 posts)
        "extra_categories": [370],  # crochet-free-patterns (155 posts)
        "search": "amigurumi",
    },
]

RAW_BASE = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
HEADERS = {"User-Agent": "AICrochet/1.0 (academic research; contact: see github)"}
PER_PAGE = 20


def _get_json(url: str) -> object:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def _extract_text_and_image(post: dict) -> dict:
    """Pull plain text and first image URL from a WP REST post object."""
    content_html = post.get("content", {}).get("rendered", "")
    soup = BeautifulSoup(content_html, "html.parser")
    pattern_text = soup.get_text(separator="\n", strip=True)

    # Featured image first, then first <img> in content
    photo_url = None
    featured = post.get("_embedded", {}).get("wp:featuredmedia", [])
    if featured:
        photo_url = (
            featured[0].get("source_url")
            or featured[0].get("media_details", {}).get("sizes", {})
                        .get("medium", {}).get("source_url")
        )
    if not photo_url:
        img = soup.find("img")
        if img:
            photo_url = img.get("src") or img.get("data-src")

    return {
        "source_type": "wordpress",
        "source_url": post.get("link", ""),
        "pattern_id": str(post.get("id", "")),
        "title": BeautifulSoup(
            post.get("title", {}).get("rendered", ""), "html.parser"
        ).get_text(strip=True),
        "photo_url": photo_url,
        "pattern_text": pattern_text,
    }


def _scrape_source(source: dict, limit: int = None) -> int:
    label = source["label"]
    base = source["base_url"]
    raw_dir = RAW_BASE / label
    raw_dir.mkdir(parents=True, exist_ok=True)

    seen = {f.stem for f in raw_dir.glob("*.json")}
    collected = 0
    page = 1

    # Build category filter: try primary categories first, then fall back to extras
    cat_ids = source.get("categories", [])
    extra_ids = source.get("extra_categories", [])
    search = source.get("search", "")

    def _fetch_page(categories, pg):
        params = {
            "per_page": PER_PAGE,
            "page": pg,
            "_embed": "wp:featuredmedia",
        }
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)
        if search:
            params["search"] = search
        url = f"{base}/wp-json/wp/v2/posts?" + urllib.parse.urlencode(params)
        return _get_json(url)

    for cat_group in [cat_ids, extra_ids] if extra_ids else [cat_ids]:
        page = 1
        while True:
            try:
                posts = _fetch_page(cat_group, page)
            except Exception as exc:
                logger.warning("[%s] Page %d fetch failed: %s", label, page, exc)
                break

            if not posts:
                break

            for post in posts:
                pid = str(post.get("id", ""))
                if pid in seen:
                    logger.debug("[%s] Skip already-seen post %s", label, pid)
                    continue

                record = _extract_text_and_image(post)
                out = raw_dir / f"{pid}.json"
                out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
                seen.add(pid)
                collected += 1
                logger.info("[%s] Saved post %s — %s (%d total)", label, pid, record["title"][:50], collected)

                if limit and collected >= limit:
                    return collected

            page += 1
            time.sleep(0.5)

    return collected


def run(limit: int = None):
    """Scrape all configured WordPress sources."""
    total = 0
    for source in SOURCES:
        logger.info("Scraping source: %s", source["label"])
        n = _scrape_source(source, limit=limit)
        total += n
        logger.info("Source %s complete: %d records", source["label"], n)
    logger.info("Total collected: %d", total)
    return total
