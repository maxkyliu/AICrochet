# flat-disc-construction Specification

## Purpose
Define how `flat_disc` parts are compiled into shaped, row-based crochet instructions that follow the diameter profile (leaf/teardrop), and how plural/paired part names produce "(make 2)".

## Requirements

### Requirement: flat_disc parts use flat-row construction
The grammar engine SHALL generate flat-row (chain foundation, back-and-forth) crochet instructions for parts with `primitive_type == "flat_disc"`, not magic-ring spiral instructions. Row widths SHALL follow the part's diameter profile so the finished piece is shaped (leaf/teardrop/triangle) rather than a fixed-width rectangle: each row's target stitch width is derived from its corresponding diameter, and width changes between consecutive rows are accomplished by edge increases (2 sc in the first and last stitch) or edge decreases (sc2tog at each end). The output SHALL include a closing note `Do NOT stuff. Sew flat.` Plural or paired part names (e.g. "Ears", "Eyes", "Wings", "Fins") SHALL emit `(make 2)` and the displayed part label SHALL be singularized.

#### Scenario: flat_disc outputs chain foundation matching first row width
- **WHEN** `compile_part` processes a `flat_disc` part whose first-row target width is `w1`
- **THEN** the first instruction SHALL be `Ch {w1+1}, turn`

#### Scenario: flat_disc outputs flat rows
- **WHEN** `compile_part` processes a `flat_disc` part
- **THEN** subsequent instructions SHALL be labeled `Row 1:`, `Row 2:`, etc. (not `Rnd N:`)
- **AND** Row 1 SHALL be `sc in 2nd ch from hook, sc across [{w1}]`

#### Scenario: flat_disc row count matches profile length
- **WHEN** the diameter profile for a `flat_disc` has N entries
- **THEN** the flat construction SHALL emit N rows total

#### Scenario: flat_disc increases when next row is wider
- **WHEN** a row's target width is greater than the previous row's width
- **THEN** the row instruction includes an edge increase pattern (e.g. `2 sc in first st, sc across, 2 sc in last st`) producing a wider row count `[{w_next}]`

#### Scenario: flat_disc decreases when next row is narrower
- **WHEN** a row's target width is less than the previous row's width
- **THEN** the row instruction includes an edge decrease pattern (e.g. `sc2tog, sc across, sc2tog`) producing a narrower row count `[{w_next}]`

#### Scenario: flat_disc plain row when width unchanged
- **WHEN** a row's target width equals the previous row's width
- **THEN** the row instruction is `Ch 1, turn, sc in each st across [{w}]`

#### Scenario: flat_disc includes sewing instruction
- **WHEN** `compile_part` finishes a `flat_disc` part
- **THEN** the final line SHALL be `Do NOT stuff. Sew flat.`

#### Scenario: flat_disc does not emit magic ring
- **WHEN** `compile_part` processes a `flat_disc` part
- **THEN** the output SHALL NOT contain any `magic ring` instruction

#### Scenario: plural part name gets make-2 and is singularized
- **WHEN** `compile_part` processes a `flat_disc` part whose name matches a known plural/paired keyword (case-insensitive: ears, eyes, wings, fins)
- **THEN** the header SHALL show the singular form of the name
- **AND** the pattern SHALL include `(make 2)` near the start or end so the crocheter knows to produce a pair

#### Scenario: non-plural part name does not get make-2
- **WHEN** a `flat_disc` part name is not a known plural/paired keyword (e.g. "Hat Brim", "Button Nose")
- **THEN** the output SHALL NOT contain `(make 2)` and the name SHALL NOT be singularized
