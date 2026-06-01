"""US vs UK crochet terminology detector."""

import re

_US_MARKERS = re.compile(
    r"\b(US\s+terms?|single\s+crochet|sc\b|half\s+double\s+crochet|hdc\b)", re.IGNORECASE
)
_UK_MARKERS = re.compile(
    r"\b(UK\s+terms?|double\s+crochet\b(?!\s+\w+\s+crochet))", re.IGNORECASE
)
_AMBIGUOUS_MARKERS = re.compile(r"\b(dc)\b")


def detect_terminology(text: str) -> str:
    """Return 'US', 'UK', or 'ambiguous'."""
    has_us = bool(_US_MARKERS.search(text))
    has_uk = bool(_UK_MARKERS.search(text))

    if has_us and not has_uk:
        return "US"
    if has_uk and not has_us:
        return "UK"
    if has_uk and has_us:
        return "ambiguous"

    # No explicit markers: look for bare 'dc' which is ambiguous in context
    if _AMBIGUOUS_MARKERS.search(text):
        return "ambiguous"

    # Default: assume US (most online amigurumi patterns are US)
    return "US"


def normalize_to_us(text: str, terminology: str) -> str:
    """Translate UK stitch names to US equivalents when terminology is UK."""
    if terminology != "UK":
        return text
    replacements = [
        (re.compile(r"\bdc\b"), "sc"),
        (re.compile(r"\bhtr\b"), "hdc"),
        (re.compile(r"\btr\b"), "dc"),
        (re.compile(r"\bdtr\b"), "tr"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = pattern.sub(replacement, result)
    return result
