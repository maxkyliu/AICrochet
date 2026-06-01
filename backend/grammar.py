import math

MIN_STITCHES = 6

# Names that, when the LLM emits a single plural part, imply a symmetric pair.
# Lowercase, match by exact whole-name equality. Multi-word names (e.g. "Left Ear",
# "Hat Brim") deliberately do not match — those are unambiguous single pieces.
_PLURAL_PAIRED = {"ears", "eyes", "wings", "fins"}


class CrochetGrammar:
    def __init__(self, stitch_width_cm=1.0, stitch_height_cm=1.0):
        self.w = stitch_width_cm
        self.h = stitch_height_cm

    def generate_round(self, prev_count, target_count):
        delta = target_count - prev_count
        if prev_count <= 0:
            return f"6 sc in magic ring [6]", 6
        if delta == 0:
            return f"sc in each st around [{target_count}]", target_count
        if delta > 0:
            if delta > prev_count:
                # More increases than available stitches — use multi-sc-per-stitch notation.
                if target_count % prev_count == 0:
                    n = target_count // prev_count
                    return f"{n} sc in each st around [{target_count}]", target_count
                # Non-exact multiple: cap to one increase per stitch and accept the adjustment.
                capped = prev_count * 2
                return f"(inc) x {prev_count} [{capped}]", capped
            interval = prev_count // delta
            sc_count = interval - 1
            if sc_count > 0:
                return f"(sc {sc_count}, inc) x {delta} [{target_count}]", target_count
            return f"(inc) x {delta} [{target_count}]", target_count
        if delta < 0:
            delta_abs = abs(delta)
            interval = prev_count // delta_abs if delta_abs <= prev_count // 2 else 2
            sc_count = interval - 2
            if sc_count > 0:
                return f"(sc {sc_count}, dec) x {delta_abs} [{target_count}]", target_count
            return f"(dec) x {delta_abs} [{target_count}]", target_count

    @staticmethod
    def _singularize_and_make2(name):
        """Plural/paired names emit (make 2) and a singularized display label.

        Conservative: only fires for bare plurals in _PLURAL_PAIRED. Multi-word
        names like "Left Ear" or "Hat Brim" are passed through unchanged.
        """
        if name.lower() in _PLURAL_PAIRED:
            return name[:-1], True   # drop trailing 's'
        return name, False

    @staticmethod
    def _flat_row_body(prev, new):
        """Return the row body (without 'Ch 1, turn,' prefix) that takes a row
        from width `prev` to width `new` with edge increases/decreases."""
        delta = new - prev
        if delta == 0:
            return "sc in each st across"
        if delta > 0:
            a = (delta + 1) // 2   # increases at the left edge
            b = delta - a          # increases at the right edge
            parts = []
            if a == 1: parts.append("2 sc in first st")
            elif a >= 2: parts.append(f"2 sc in each of first {a} sts")
            if b == 0:
                parts.append("sc across")
            else:
                parts.append(f"sc across to last {b} st" + ("s" if b > 1 else ""))
            if b == 1: parts.append("2 sc in last st")
            elif b >= 2: parts.append(f"2 sc in each of last {b} sts")
            return ", ".join(parts)
        d = -delta
        a = (d + 1) // 2
        b = d - a
        parts = []
        if a == 1: parts.append("sc2tog")
        elif a >= 2: parts.append(f"sc2tog x {a}")
        if b == 0:
            parts.append("sc across")
        else:
            parts.append(f"sc across to last {2 * b} sts")
        if b == 1: parts.append("sc2tog")
        elif b >= 2: parts.append(f"sc2tog x {b}")
        return ", ".join(parts)

    def _compile_flat_disc(self, name, target_diameters):
        # Per-row target widths from the diameter profile. Halved circumference
        # because a flat sheet only shows ~half the cylinder's wrap.
        widths = [max(1, round((d * math.pi) / self.w / 2)) for d in target_diameters]

        display_name, make2 = self._singularize_and_make2(name)
        pattern = [f"--- {display_name.upper()} ---"]
        if make2:
            pattern.append("(make 2)")

        w1 = widths[0]
        pattern.append(f"Ch {w1 + 1}, turn")
        pattern.append(f"Row 1: sc in 2nd ch from hook, sc across [{w1}]")

        prev = w1
        for i, w in enumerate(widths[1:], start=2):
            body = self._flat_row_body(prev, w)
            pattern.append(f"Row {i}: Ch 1, turn, {body} [{w}]")
            prev = w

        pattern.append("Do NOT stuff. Sew flat.")
        return pattern

    def compile_part(self, name, target_diameters, primitive_type="sphere"):
        return self.compile_part_detailed(name, target_diameters, primitive_type)[0]

    def compile_part_detailed(self, name, target_diameters, primitive_type="sphere"):
        """Like compile_part but also returns the actual per-round stitch counts used.

        Returns (instructions, round_counts). For flat_disc, round_counts is empty
        (flat sheets are not round-based and are not 3D-refined).
        """
        if primitive_type == "flat_disc":
            return self._compile_flat_disc(name, target_diameters), []

        counts = [max(MIN_STITCHES, MIN_STITCHES * round(((d * math.pi) / self.w) / MIN_STITCHES)) for d in target_diameters]
        pattern = [f"--- {name.upper()} ---"]
        round_counts = []
        current = 0
        closed = False
        for i, target in enumerate(counts):
            instr, current = self.generate_round(current, target)
            pattern.append(f"Rnd {i+1}: {instr}")
            round_counts.append(current)
            if i > 0 and current <= MIN_STITCHES and counts[i] < counts[i - 1]:
                pattern.append("sl st to first st, fasten off")
                closed = True
                break

        # Every 3D part needs a terminal closure + stuffing instruction so the
        # crocheter knows whether to stuff, close, or sew. flat_disc is handled
        # separately and never reaches here.
        if not closed and round_counts:
            if round_counts[-1] <= MIN_STITCHES:
                pattern.append("Stuff firmly.")
                pattern.append("Fasten off, weave tail through remaining sts to close.")
            else:
                pattern.append("Stuff before sewing.")
                pattern.append("Fasten off, leave a long tail for sewing.")
        elif closed:
            # Tapered close path: insert a stuffing note before the existing fasten-off.
            pattern.insert(-1, "Stuff firmly.")
        return pattern, round_counts
