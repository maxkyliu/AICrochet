"""Core normalizer: orchestrates terminology detection, tokenization, and diameter reconstruction."""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.normalizer.terminology import detect_terminology, normalize_to_us
from data.normalizer.tokenizer import tokenize_round
from data.normalizer.diameter import detect_parts, reconstruct_diameter_profile, compute_quality_score
from data.normalizer.labeler import is_noise_record, infer_scale, label_primitive

logger = logging.getLogger(__name__)

MIN_ROUNDS = 3          # a usable diameter profile needs at least 3 rounds
MAX_FIRST_ROUND = 12    # rounds start from a magic ring / small chain circle
MAX_COUNT = 200         # sanity cap on any single round's stitch count


def _accept_round_line(tok: dict) -> bool:
    """A line counts as a round only if it carries real round evidence:
    a Rnd/Row prefix, a stated total, or a magic-ring start. This keeps
    prose lines ('Stuff the head', materials lists) out of the profile."""
    if not tok["tokens"]:
        return False
    if tok["has_round_prefix"] or tok["stated_total"] is not None:
        return True
    return any("magic_ring" in t for t in tok["tokens"])


def _extract_stitch_counts(round_lines: list) -> tuple:
    """Walk a part's lines carrying the running count forward.

    Returns (stitch_counts, stated_fraction, checksum_ok_fraction).
    Stated totals are trusted over computed totals: pattern authors write
    them explicitly and our op parser can't expand every notation.
    """
    counts = []
    stated = 0
    checksum_ok = 0
    checked = 0
    prev = None
    for line in round_lines:
        tok = tokenize_round(line, prev_count=prev)
        if not _accept_round_line(tok):
            continue
        if tok["stated_total"] is not None:
            count = tok["stated_total"]
            stated += 1
            if tok["computed_total"] > 0:
                checked += 1
                if tok["computed_total"] == count:
                    checksum_ok += 1
        else:
            count = tok["computed_total"]
        if count <= 0 or count > MAX_COUNT:
            continue
        counts.append(count)
        prev = count

    n = len(counts)
    stated_fraction = stated / n if n else 0.0
    checksum_fraction = checksum_ok / checked if checked else 1.0
    return counts, stated_fraction, checksum_fraction


def _is_feasible(counts: list) -> bool:
    """Enforce crochet geometry: every round is between half (all-dec) and
    double (all-inc) its predecessor, and worked parts start small."""
    if counts[0] > MAX_FIRST_ROUND:
        return False
    for prev, curr in zip(counts, counts[1:]):
        if curr > 2 * prev or 2 * curr < prev:
            return False
    return True


def normalize_pattern(raw_record: dict) -> list:
    """Normalize one raw scraped record into per-part training records.

    Returns a list of dicts ready to insert into training_records table.
    Returns an empty list if the record cannot be normalized.
    """
    source_type = raw_record.get("source_type", "unknown")
    source_url = raw_record.get("source_url", "")
    pattern_id = raw_record.get("pattern_id") or raw_record.get("id", "")
    pattern_text = raw_record.get("pattern_text") or raw_record.get("notes") or ""

    if not pattern_text.strip():
        logger.debug("Empty pattern text for %s; skipping", source_url)
        return []

    terminology = detect_terminology(pattern_text)
    if terminology == "ambiguous":
        logger.debug("Ambiguous terminology in %s; will still process with penalty", source_url)

    normalized_text = normalize_to_us(pattern_text, terminology)
    parts = detect_parts(normalized_text)

    if not parts or (len(parts) == 1 and parts[0][0] is None and len(parts[0][1]) < 3):
        logger.debug("No clear parts found in %s; skipping", source_url)
        return []

    output_records = []
    for part_name, round_lines in parts:
        effective_name = part_name or "Unknown"

        if is_noise_record(effective_name):
            logger.debug("Noise record skipped: '%s' in %s", effective_name, source_url)
            continue

        stitch_counts, stated_fraction, checksum_ok = _extract_stitch_counts(round_lines)

        if len(stitch_counts) < MIN_ROUNDS:
            logger.debug("Too few rounds for part '%s' in %s", effective_name, source_url)
            continue
        if not _is_feasible(stitch_counts):
            logger.debug("Infeasible profile for part '%s' in %s: %s",
                         effective_name, source_url, stitch_counts)
            continue

        diameters = reconstruct_diameter_profile(stitch_counts)
        quality = compute_quality_score(terminology, stated_fraction, checksum_ok)
        primitive_type = label_primitive(effective_name, stitch_counts)
        scale = infer_scale(stitch_counts)

        output_records.append({
            "source_type": source_type,
            "source_url": source_url,
            "pattern_id": str(pattern_id),
            "part_name": effective_name,
            "primitive_type": primitive_type,
            "scale": scale,
            "diameter_profile": diameters,
            "stitch_counts": stitch_counts,
            "terminology": terminology,
            "quality_score": quality,
            "is_synthetic": False,
        })

    return output_records
