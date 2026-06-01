"""Tests for the readability fixes in CrochetGrammar.

Covers F3 (every 3D part gets terminal closure + stuffing) and F4 (flat_disc
follows the diameter profile with edge shaping; plural parts get make-2).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from grammar import CrochetGrammar


def _last_lines(pattern, n=4):
    return pattern[-n:]


# ─── F3: terminal closure + stuffing for every 3D part ────────────────────────

class TestTerminalClosure:
    def setup_method(self):
        self.g = CrochetGrammar()

    def test_open_cylinder_gets_stuff_and_sewing_tail(self):
        pat = self.g.compile_part("Leg", [8, 8, 8, 8, 8, 8], "cylinder")
        assert "Stuff before sewing." in pat
        assert any("leave a long tail for sewing" in ln.lower() for ln in pat)
        # The pattern must not just end on a bare round.
        assert not pat[-1].startswith("Rnd ")

    def test_open_capsule_arm_gets_closure(self):
        pat = self.g.compile_part("Arm", [2, 4, 6, 8, 8, 8, 8, 6], "capsule")
        # Last round ends above MIN_STITCHES → open-end variant.
        assert "Stuff before sewing." in pat
        assert any("leave a long tail" in ln.lower() for ln in pat)

    def test_tapered_sphere_keeps_existing_close_and_adds_stuffing(self):
        pat = self.g.compile_part("Head", [2, 4, 6, 8, 8, 8, 6, 4, 2], "sphere")
        # Existing tapered-close instruction stays.
        assert "sl st to first st, fasten off" in pat
        # A stuffing note now precedes it.
        idx_close = pat.index("sl st to first st, fasten off")
        assert "Stuff firmly." in pat[:idx_close]


# ─── F4: shaped rows + make-2 ────────────────────────────────────────────────

class TestFlatDiscShapedRows:
    def setup_method(self):
        self.g = CrochetGrammar()

    def test_widens_when_profile_grows(self):
        pat = self.g.compile_part("Ear", [1, 3, 5], "flat_disc")
        # Row 2 must use edge-increase phrasing and produce a wider count than row 1.
        row1 = next(ln for ln in pat if ln.startswith("Row 1:"))
        row2 = next(ln for ln in pat if ln.startswith("Row 2:"))
        assert "2 sc in" in row2, f"Row 2 should widen, got: {row2}"
        w1 = int(row1.split("[")[1].rstrip("]"))
        w2 = int(row2.split("[")[1].rstrip("]"))
        assert w2 > w1

    def test_widens_then_tapers_leaf_shape(self):
        pat = self.g.compile_part("Ear", [1, 3, 5, 5, 3, 1], "flat_disc")
        # Find row widths.
        widths = [int(ln.split("[")[1].rstrip("]")) for ln in pat if ln.startswith("Row ")]
        assert widths == sorted(widths[: widths.index(max(widths)) + 1]) + sorted(
            widths[widths.index(max(widths)) + 1 :], reverse=True
        ), f"widths should grow then shrink, got {widths}"
        # Tapering rows use sc2tog phrasing.
        assert any("sc2tog" in ln for ln in pat)

    def test_plural_ears_gets_make_2_and_singular_label(self):
        pat = self.g.compile_part("Ears", [1, 3, 5], "flat_disc")
        assert "--- EAR ---" in pat, f"header should be singularized to EAR, got {pat[0]}"
        assert "(make 2)" in pat

    def test_non_plural_does_not_get_make_2(self):
        pat = self.g.compile_part("Hat Brim", [3, 5, 5], "flat_disc")
        assert "--- HAT BRIM ---" in pat
        assert "(make 2)" not in pat

    def test_flat_disc_keeps_sew_flat_ending(self):
        pat = self.g.compile_part("Ear", [1, 3, 5], "flat_disc")
        assert pat[-1] == "Do NOT stuff. Sew flat."

    def test_flat_disc_does_not_get_3d_stuffing_block(self):
        pat = self.g.compile_part("Ear", [1, 3, 5], "flat_disc")
        # The 3D-part stuffing notes must not leak into flat_disc.
        assert "Stuff firmly." not in pat
        assert "Stuff before sewing." not in pat
