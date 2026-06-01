## ADDED Requirements

### Requirement: Stitch instructions contain no zero-stitch terms
The grammar engine SHALL never emit `sc 0` in any stitch instruction. When the interval between increases or decreases is 1 (every stitch is an increase or decrease), the notation SHALL omit the `sc` term entirely.

#### Scenario: Every stitch is an increase
- **WHEN** `generate_round` produces an increase round where `delta == prev_count` (interval == 1)
- **THEN** the instruction SHALL be `(inc) x {delta} [{target_count}]`, not `(sc 0, inc) x {delta}`

#### Scenario: Every other stitch is an increase (interval > 1)
- **WHEN** `generate_round` produces an increase round where interval > 1
- **THEN** the instruction SHALL be `(sc {interval-1}, inc) x {delta} [{target_count}]` with `interval-1 >= 1`

#### Scenario: Every stitch is a decrease
- **WHEN** `generate_round` produces a decrease round where the effective sc count before dec is 0
- **THEN** the instruction SHALL be `(dec) x {delta_abs} [{target_count}]`, not `(sc 0, dec) x {delta_abs}`

#### Scenario: Normal decrease with sc terms
- **WHEN** `generate_round` produces a decrease round where `interval - 2 > 0`
- **THEN** the instruction SHALL be `(sc {interval-2}, dec) x {delta_abs} [{target_count}]` with `interval-2 >= 1`
