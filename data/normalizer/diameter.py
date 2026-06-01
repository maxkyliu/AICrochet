"""Diameter reconstruction and part boundary detection."""

import math
import re
import logging

logger = logging.getLogger(__name__)

STITCH_WIDTH_CM = 1.0  # default; will be overridden by gauge when available

# Part boundary patterns: "--- HEAD ---", "**HEAD**", "Head:", "## Head"
_PART_BOUNDARY_RE = re.compile(
    r"(?:^|\n)\s*(?:---+\s*)?([A-Z][A-Za-z\s]{1,30})(?:\s*---+|:|\*\*|##)?\s*(?:\n|$)"
)
_RAVELRY_SECTION_RE = re.compile(
    r"(?:^|\n)#+\s*([A-Z][A-Za-z\s]{1,30})\s*(?:\n|$)"
)


def stitch_count_to_diameter(stitch_count: int, stitch_width_cm: float = STITCH_WIDTH_CM) -> float:
    """Convert a per-round stitch count to a diameter using C = π × d."""
    return (stitch_count * stitch_width_cm) / math.pi


def reconstruct_diameter_profile(stitch_counts: list, stitch_width_cm: float = STITCH_WIDTH_CM) -> list:
    """Convert a list of per-round stitch counts to a diameter profile."""
    return [stitch_count_to_diameter(n, stitch_width_cm) for n in stitch_counts]


def detect_parts(pattern_text: str) -> list:
    """Split pattern text into named parts.

    Returns a list of (part_name, [round_instruction_strings]) tuples.
    Returns [(None, all_lines)] if no boundaries are found.
    """
    parts = []

    # Try explicit boundary markers first
    segments = re.split(_PART_BOUNDARY_RE, pattern_text)
    if len(segments) > 1:
        # segments alternates: [pre, name, content, name, content, ...]
        i = 1
        while i < len(segments) - 1:
            name = segments[i].strip()
            content = segments[i + 1] if i + 1 < len(segments) else ""
            rounds = [line.strip() for line in content.splitlines() if line.strip()]
            if rounds:
                parts.append((name, rounds))
            i += 2
        return parts

    # Try Ravelry markdown-style headings
    segments = re.split(_RAVELRY_SECTION_RE, pattern_text)
    if len(segments) > 1:
        i = 1
        while i < len(segments) - 1:
            name = segments[i].strip()
            content = segments[i + 1] if i + 1 < len(segments) else ""
            rounds = [line.strip() for line in content.splitlines() if line.strip()]
            if rounds:
                parts.append((name, rounds))
            i += 2
        return parts

    # No boundaries found
    all_lines = [line.strip() for line in pattern_text.splitlines() if line.strip()]
    return [(None, all_lines)]


def compute_quality_score(
    part_rounds: list,
    terminology: str,
    all_checksums_valid: bool,
) -> float:
    """Score a normalized record 0.0–1.0.

    Deductions:
      - ambiguous terminology: -0.2
      - any checksum failure:  -0.3
      - very few rounds (<3): -0.2
    """
    score = 1.0
    if terminology == "ambiguous":
        score -= 0.2
    if not all_checksums_valid:
        score -= 0.3
    if len(part_rounds) < 3:
        score -= 0.2
    return max(0.0, score)
