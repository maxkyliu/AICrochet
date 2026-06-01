## MODIFIED Requirements

### Requirement: Grammar closes parts at minimum stitch count
The grammar engine SHALL stop emitting crochet rounds once the stitch count has decreased to or below the minimum stitch count (6) and append a closing instruction `sl st to first st, fasten off`. Additionally, every 3D part (any `primitive_type` other than `flat_disc`) SHALL end with a terminal closure even when it does not decrease to the minimum: parts whose final round count is at or below the minimum SHALL close with a tail-cinch instruction, and parts whose final round count is above the minimum (open-ended tubes such as arms or legs) SHALL be told to fasten off and leave a tail for sewing. Every 3D part SHALL also include a stuffing note appropriate to its end state. No 3D part may end without a terminal closure instruction.

#### Scenario: Shape decreasing to minimum
- **WHEN** `compile_part` processes a profile where stitch count reaches 6 or fewer during a decreasing phase
- **THEN** the round reaching minimum is emitted, followed by `sl st to first st, fasten off`, and no further rounds are emitted

#### Scenario: Dead rounds not emitted
- **WHEN** the learned model or hardcoded profile contains additional entries after the shape closes
- **THEN** those entries MUST NOT appear in the compiled pattern output

#### Scenario: Cylinder with flat profile not terminated early
- **WHEN** all rounds in the profile have the same stitch count above minimum
- **THEN** all rounds SHALL be emitted without a premature terminator (terminator only applies when actively decreasing to minimum)

#### Scenario: Open-ended tube gets terminal closure
- **WHEN** `compile_part` finishes a 3D part whose final round count is above the minimum (e.g. a cylinder leg ending at [8] or a capsule arm ending at [12])
- **THEN** the pattern ends with a stuffing note and a fasten-off instruction that tells the crocheter to leave a tail for sewing
- **AND** the pattern does NOT end on a bare stitch round with no closure

#### Scenario: Tapered part gets stuffing note before closing
- **WHEN** `compile_part` finishes a 3D part that decreases to the minimum
- **THEN** a stuffing note appears before the final close-and-fasten-off instruction

#### Scenario: flat_disc unaffected by 3D closure
- **WHEN** `compile_part` processes a `flat_disc` part
- **THEN** the new 3D closure/stuffing instructions are NOT added; the flat_disc keeps its own `Do NOT stuff. Sew flat.` ending
