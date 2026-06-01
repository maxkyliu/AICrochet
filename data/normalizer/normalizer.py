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

        tokenized = [tokenize_round(line) for line in round_lines]
        stitch_counts = []
        all_valid = True

        for tok in tokenized:
            if tok["computed_total"] > 0:
                stitch_counts.append(tok["computed_total"])
            if not tok["valid"]:
                all_valid = False

        if not stitch_counts:
            logger.debug("No valid stitch counts for part '%s' in %s", effective_name, source_url)
            continue

        diameters = reconstruct_diameter_profile(stitch_counts)
        quality = compute_quality_score(round_lines, terminology, all_valid)
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
