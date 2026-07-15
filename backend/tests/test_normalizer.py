import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.normalizer.tokenizer import tokenize_round
from data.normalizer.normalizer import (
    _extract_stitch_counts,
    _is_feasible,
    normalize_pattern,
)


class TestTokenizerStatedTotals:
    def test_stated_total_at_line_end(self):
        tok = tokenize_round("Ch 1. Work 2 sc into each st around. Join to first sc with sl st. (12)")
        assert tok["stated_total"] == 12

    def test_stated_total_with_sts_suffix(self):
        tok = tokenize_round("sc in each st around (24 sts)")
        assert tok["stated_total"] == 24

    def test_bracket_repetition_with_trailing_multiplier(self):
        # 1dogwoof notation: "[1 sc, inc] 6x"
        tok = tokenize_round("Ch 1. Work [1 sc, inc] 6x around. (18)")
        assert tok["stated_total"] == 18
        assert tok["computed_total"] == 18
        assert tok["valid"]

    def test_paren_repetition_with_x_prefix(self):
        tok = tokenize_round("Rnd 3: (sc 1, inc) x 6 [18]")
        assert tok["stated_total"] == 18
        assert tok["computed_total"] == 18

    def test_each_st_around_resolved_from_prev_count(self):
        tok = tokenize_round("sc in each st around", prev_count=24)
        assert tok["computed_total"] == 24

    def test_2sc_each_st_doubles_prev_count(self):
        tok = tokenize_round("Work 2 sc into each st around.", prev_count=6)
        assert tok["computed_total"] == 12

    def test_join_clause_not_counted(self):
        tok = tokenize_round("6 sc in magic ring. Join to first sc with sl st.")
        assert tok["computed_total"] == 6

    def test_round_prefix_detected(self):
        assert tokenize_round("Rnd 2: (inc) x 6 [12]")["has_round_prefix"]
        assert not tokenize_round("Stuff the head firmly")["has_round_prefix"]


class TestExtraction:
    def test_prose_lines_excluded(self):
        counts, _, _ = _extract_stitch_counts([
            "Worked in seamed rounds.",
            "Round 1: Work 6 sc into a magic circle. (6)",
            "Round 2: Work 2 sc into each st around. (12)",
            "Stuff the head firmly before closing.",
            "Round 3: [1 sc, inc] 6x around. (18)",
        ])
        assert counts == [6, 12, 18]

    def test_stated_totals_preferred_over_parse(self):
        counts, stated_fraction, _ = _extract_stitch_counts([
            "Rnd 1: 6 sc in magic ring [6]",
            "Rnd 2: work an unusual bobble stitch combo around [12]",
        ])
        assert counts == [6, 12]
        assert stated_fraction == 1.0


class TestFeasibility:
    def test_valid_sphere_profile(self):
        assert _is_feasible([6, 12, 18, 24, 24, 18, 12, 6])

    def test_rejects_more_than_double_jump(self):
        assert not _is_feasible([6, 18, 24])

    def test_rejects_large_first_round(self):
        assert not _is_feasible([30, 32, 34])


class TestNormalizePattern:
    _PATTERN = """
HEAD
Round 1: Work 6 sc into a magic circle. Join to first sc with sl st. (6)
Round 2: Ch 1. Work 2 sc into each st around. Join to first sc with sl st. (12)
Round 3: Ch 1. Work [1 sc, inc] 6x around. Join to first sc with sl st. (18)
Round 4: Ch 1. Work 1 sc in each st around. Join to first sc with sl st. (18)
Round 5: Ch 1. Work [1 sc, dec] 6x around. Join to first sc with sl st. (12)
Scissors
Yarn needle
"""

    def test_extracts_correct_counts_and_drops_noise(self):
        records = normalize_pattern({
            "source_type": "test", "source_url": "u", "pattern_id": "1",
            "pattern_text": self._PATTERN,
        })
        assert len(records) == 1
        rec = records[0]
        assert rec["part_name"] == "HEAD"
        assert rec["stitch_counts"] == [6, 12, 18, 18, 12]
        assert rec["primitive_type"] == "sphere"
        assert rec["quality_score"] >= 0.7
