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

# Repetition block, both bracket styles and both multiplier orders:
# "(sc 2, inc) x 6", "[1 sc, inc] 6x", "(sc, inc) 6 times"
_REP_RE = re.compile(
    r"[\(\[]([^\)\]]+)[\)\]]\s*(?:[x×\*]\s*(\d+)|(\d+)\s*(?:[x×]|times)\b)",
    re.IGNORECASE,
)

# Stated stitch count: "[24]", "(24)", "(24 sts)", "= 24 sts", "– 24 sts".
# Matched against the tail of the line; the LAST occurrence wins.
_TOTAL_RE = re.compile(r"[\[\(](\d+)(?:\s*sts?\.?)?[\]\)]|[=–—-]\s*(\d+)\s*sts?\b", re.IGNORECASE)

# Round prefix stripper: "Rnd 3:", "Row 3:", "Round 3:", "R3:"
_ROUND_PREFIX_RE = re.compile(r"^(rnd|row|round|r)\s*\.?\s*\d+\s*:?\s*", re.IGNORECASE)

# Trailing join clause: "Join to first sc with sl st." — bookkeeping, not stitches.
_JOIN_CLAUSE_RE = re.compile(r"\bjoin\b[^.]*\.?", re.IGNORECASE)

# "each st around/across" semantics (resolved against the previous round's count):
# "sc in each st around" → prev sc; "2 sc in each st around" → prev inc.
_EACH_ST_RE = re.compile(
    r"(?:(\d+)\s*)?(sc|inc|dec|sc2tog)\s+(?:in(?:to)?\s+)?(?:blo\s+of\s+|flo\s+of\s+)?each\s+st(?:itch)?\s*(?:around|across)?",
    re.IGNORECASE,
)


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
        times = int(m.group(2) or m.group(3))
        return (inner.strip() + ", ") * times

    expanded = _REP_RE.sub(_expand, text)
    return expanded


def _resolve_each_st(text: str, prev_count: int) -> list:
    """Resolve '<op> in each st around' against the previous round's count.

    Returns the token list for the whole-round op, or [] if no match.
    """
    m = _EACH_ST_RE.search(text)
    if not m:
        return []
    multiplier = int(m.group(1)) if m.group(1) else 1
    op_raw = m.group(2).lower()
    if op_raw == "sc" and multiplier >= 2:
        # "2 sc in each st" = an increase in every stitch
        return [{OP_INC: prev_count}]
    if op_raw == "inc":
        return [{OP_INC: prev_count}]
    if op_raw in ("dec", "sc2tog"):
        return [{OP_DEC: prev_count // 2}]
    return [{OP_SC: prev_count}]


def tokenize_round(instruction: str, prev_count: int | None = None) -> dict:
    """Parse a single round instruction.

    prev_count: stitch count of the previous round, used to resolve
    "each st around" instructions. None disables that resolution.

    Returns:
        {
          "tokens": [{"sc": 2}, {"inc": 1}, ...],
          "stated_total": 24 or None,
          "computed_total": 24,
          "valid": True/False,
          "has_round_prefix": True/False,
        }
    """
    # Strip round prefix
    stripped = instruction.strip()
    clean = _ROUND_PREFIX_RE.sub("", stripped)
    has_round_prefix = clean != stripped

    # Extract stated total (last occurrence on the line wins)
    stated_total = None
    for total_match in _TOTAL_RE.finditer(clean):
        stated_total = int(total_match.group(1) or total_match.group(2))
        last_span = total_match.span()
    if stated_total is not None:
        clean = (clean[: last_span[0]] + clean[last_span[1]:]).strip()

    # Drop join bookkeeping so "Join to first sc" doesn't count as a stitch
    clean = _JOIN_CLAUSE_RE.sub("", clean)

    # Expand repetition blocks
    expanded = _expand_repetitions(clean)

    # Parse tokens: whole-round "each st" form first, generic op scan otherwise
    tokens = []
    if prev_count and prev_count > 0 and not _MAGIC_RING_RE.search(expanded):
        tokens = _resolve_each_st(expanded, prev_count)
    if not tokens:
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
        "has_round_prefix": has_round_prefix,
    }


def tokenize_pattern_part(rounds_text: list) -> list:
    """Tokenize a list of round instruction strings for one pattern part,
    carrying the running stitch count forward between rounds."""
    results = []
    prev = None
    for line in rounds_text:
        if not line.strip():
            continue
        tok = tokenize_round(line, prev_count=prev)
        results.append(tok)
        best = tok["stated_total"] if tok["stated_total"] is not None else tok["computed_total"]
        if best > 0:
            prev = best
    return results
