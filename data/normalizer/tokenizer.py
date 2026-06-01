"""Crochet instruction tokenizer.

Converts a round instruction string into a canonical list of operation tokens,
expanding repetition blocks and mapping all notation variants to standard ops.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Canonical op names
OP_SC = "sc"
OP_INC = "inc"
OP_DEC = "dec"
OP_CH = "ch"
OP_SL_ST = "sl_st"
OP_MAGIC_RING = "magic_ring"

# Increase notation variants → inc
_INC_PATTERNS = [
    re.compile(r"2\s*sc\s+in\s+(same|next)\s+st", re.IGNORECASE),
    re.compile(r"inc\s+in\s+next\s+st", re.IGNORECASE),
    re.compile(r"\*\s*2\s*sc\s*\*", re.IGNORECASE),
    re.compile(r"\binc\b", re.IGNORECASE),
]

# Decrease notation variants → dec
_DEC_PATTERNS = [
    re.compile(r"sc2?tog(?:ether)?", re.IGNORECASE),
    re.compile(r"inv(?:isible)?\s+dec(?:rease)?", re.IGNORECASE),
    re.compile(r"\bdec\b", re.IGNORECASE),
]

# Magic ring variants
_MAGIC_RING_RE = re.compile(
    r"(magic\s+ring|magic\s+circle|adjustable\s+ring|mr\b)", re.IGNORECASE
)

# Repetition block: (... ) × N or (... ) x N or repeat ... N times
_REP_RE = re.compile(r"\(([^)]+)\)\s*[x×\*]\s*(\d+)", re.IGNORECASE)

# Stitch count in brackets at end of round: [24] or (24)
_TOTAL_RE = re.compile(r"[\[\(](\d+)[\]\)]$")

# Round prefix stripper: "Rnd 3:", "Row 3:", "Round 3:", "R3:"
_ROUND_PREFIX_RE = re.compile(r"^(rnd|row|round|r)\s*\.?\s*\d+\s*:?\s*", re.IGNORECASE)


def _normalize_inc_dec(text: str) -> str:
    """Replace all increase/decrease variant notations with canonical forms."""
    result = text
    for pat in _INC_PATTERNS:
        result = pat.sub("inc", result)
    for pat in _DEC_PATTERNS:
        result = pat.sub("dec", result)
    return result


def _parse_ops_from_text(text: str) -> list:
    """Extract a flat list of (op, count) tokens from a segment of text."""
    tokens = []
    text = text.strip()

    if _MAGIC_RING_RE.search(text):
        # e.g. "6 sc in magic ring"
        m = re.search(r"(\d+)\s*sc", text, re.IGNORECASE)
        count = int(m.group(1)) if m else 6
        tokens.append({OP_MAGIC_RING: count})
        return tokens

    # Normalize then tokenize individual ops
    normalized = _normalize_inc_dec(text)

    # Find all op mentions with optional preceding count
    pattern = re.compile(
        r"(\d+)?\s*(inc|dec|sc|hdc|dc|ch|sl\s*st|slip\s+stitch)\b", re.IGNORECASE
    )
    for m in pattern.finditer(normalized):
        raw_count = m.group(1)
        op_raw = m.group(2).lower().replace(" ", "_")
        count = int(raw_count) if raw_count else 1

        if "inc" in op_raw:
            op = OP_INC
        elif "dec" in op_raw:
            op = OP_DEC
        elif op_raw in ("sc",):
            op = OP_SC
        elif op_raw in ("ch",):
            op = OP_CH
        elif "sl" in op_raw:
            op = OP_SL_ST
        else:
            op = op_raw

        tokens.append({op: count})

    return tokens


def _expand_repetitions(text: str) -> str:
    """Expand (block) × N notation into repeated inline text."""
    def _expand(m):
        inner = m.group(1)
        times = int(m.group(2))
        return (inner.strip() + ", ") * times

    expanded = _REP_RE.sub(_expand, text)
    return expanded


def tokenize_round(instruction: str) -> dict:
    """Parse a single round instruction.

    Returns:
        {
          "tokens": [{"sc": 2}, {"inc": 1}, ...],
          "stated_total": 24 or None,
          "computed_total": 24,
          "valid": True/False,
        }
    """
    # Strip round prefix
    clean = _ROUND_PREFIX_RE.sub("", instruction.strip())

    # Extract stated total
    total_match = _TOTAL_RE.search(clean)
    stated_total = int(total_match.group(1)) if total_match else None
    if total_match:
        clean = clean[: total_match.start()].strip()

    # Expand repetition blocks
    expanded = _expand_repetitions(clean)

    # Parse tokens
    tokens = _parse_ops_from_text(expanded)

    # Compute total stitches produced by these tokens
    computed = sum(
        count
        for token in tokens
        for op, count in token.items()
        if op in (OP_SC, OP_INC, OP_DEC, OP_MAGIC_RING)
    )
    # inc adds 1 extra stitch
    inc_count = sum(t.get(OP_INC, 0) for t in tokens)
    computed += inc_count

    valid = (stated_total is None) or (computed == stated_total)
    if not valid:
        logger.debug(
            "Checksum mismatch: stated=%s computed=%d in '%s'",
            stated_total, computed, instruction,
        )

    return {
        "tokens": tokens,
        "stated_total": stated_total,
        "computed_total": computed,
        "valid": valid,
    }


def tokenize_pattern_part(rounds_text: list) -> list:
    """Tokenize a list of round instruction strings for one pattern part."""
    return [tokenize_round(line) for line in rounds_text if line.strip()]
