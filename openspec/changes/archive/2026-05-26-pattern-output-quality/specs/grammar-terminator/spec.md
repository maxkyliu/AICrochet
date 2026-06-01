## ADDED Requirements

### Requirement: Grammar closes parts at minimum stitch count
The grammar engine SHALL stop emitting crochet rounds once the stitch count has decreased to or below the minimum stitch count (6) and append a closing instruction. The closing instruction SHALL be `sl st to first st, fasten off`.

#### Scenario: Shape decreasing to minimum
- **WHEN** `compile_part` processes a profile where stitch count reaches 6 or fewer during a decreasing phase
- **THEN** the round reaching minimum is emitted, followed by `sl st to first st, fasten off`, and no further rounds are emitted

#### Scenario: Dead rounds not emitted
- **WHEN** the learned model or hardcoded profile contains additional entries after the shape closes
- **THEN** those entries MUST NOT appear in the compiled pattern output

#### Scenario: Cylinder with flat profile not terminated early
- **WHEN** all rounds in the profile have the same stitch count above minimum
- **THEN** all rounds SHALL be emitted without a premature terminator (terminator only applies when actively decreasing to minimum)
