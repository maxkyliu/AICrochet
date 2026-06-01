## ADDED Requirements

### Requirement: flat_disc parts use flat-row construction
The grammar engine SHALL generate flat-row (chain foundation, back-and-forth) crochet instructions for parts with `primitive_type == "flat_disc"`, not magic-ring spiral instructions. The output SHALL include a closing note `Do NOT stuff. Sew flat.`

#### Scenario: flat_disc outputs chain foundation
- **WHEN** `compile_part` processes a `flat_disc` part
- **THEN** the first instruction SHALL be `Ch {width+1}, turn` where `width = max(target_stitch_counts)`

#### Scenario: flat_disc outputs flat rows
- **WHEN** `compile_part` processes a `flat_disc` part
- **THEN** subsequent instructions SHALL be labeled `Row 1:`, `Row 2:`, etc. (not `Rnd N:`)
- **AND** Row 1 SHALL be `sc in 2nd ch from hook, sc across [{width}]`
- **AND** subsequent rows SHALL be `Ch 1, turn, sc in each st across [{width}]`

#### Scenario: flat_disc row count matches profile length
- **WHEN** the diameter profile for a `flat_disc` has N entries
- **THEN** the flat construction SHALL emit N rows total

#### Scenario: flat_disc includes sewing instruction
- **WHEN** `compile_part` finishes a `flat_disc` part
- **THEN** the final line SHALL be `Do NOT stuff. Sew flat.`

#### Scenario: flat_disc does not emit magic ring
- **WHEN** `compile_part` processes a `flat_disc` part
- **THEN** the output SHALL NOT contain any `magic ring` instruction
