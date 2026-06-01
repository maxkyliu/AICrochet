## ADDED Requirements

### Requirement: US vs UK terminology detection
The normalizer SHALL detect whether a pattern uses US or UK crochet terminology by scanning for marker phrases (e.g., "US terms", "UK terms", "double crochet" in context). Detected terminology SHALL be stored in the normalized record. Ambiguous patterns SHALL be flagged for manual review.

#### Scenario: US pattern correctly identified
- **WHEN** pattern text contains "sc" (single crochet) and no explicit UK markers
- **THEN** the normalizer assigns `terminology=US` to the record

#### Scenario: UK pattern correctly identified
- **WHEN** pattern text contains "dc" used for what US calls "sc" and the header says "UK terms"
- **THEN** the normalizer assigns `terminology=UK` and translates all stitches to US equivalents before further processing

#### Scenario: Ambiguous pattern flagged
- **WHEN** pattern text contains both "sc" and "dc" without a clear terminology declaration
- **THEN** the record is marked `terminology=ambiguous` and excluded from training until manually reviewed

---

### Requirement: Instruction tokenizer produces canonical ops
The normalizer SHALL tokenize each crochet round instruction into a sequence of canonical operation tokens. Supported tokens: `sc` (single crochet), `inc` (increase), `dec` (decrease), `ch` (chain), `sl_st` (slip stitch), `magic_ring`. Repetition blocks `(... ) × N` SHALL be expanded into flat token sequences.

#### Scenario: Standard round tokenized
- **WHEN** the normalizer processes "Rnd 3: (sc 2, inc) × 6 [24]"
- **THEN** it produces `[{op: sc, count: 2}, {op: inc, count: 1}]` repeated 6 times with total=24

#### Scenario: Increase notation variants normalized
- **WHEN** the pattern text uses "2sc in same st" or "inc in next st" or "*2sc*"
- **THEN** all variants tokenize to the same `{op: inc}` token

#### Scenario: Stitch count checksum validated
- **WHEN** a round specifies a total in brackets (e.g., "[24]")
- **THEN** the normalizer counts the expanded tokens and rejects the round if the count does not match the stated total

---

### Requirement: Diameter profile reconstruction from stitch counts
The normalizer SHALL compute a diameter profile for each pattern part by converting per-round stitch counts using the inverse circumference formula: `diameter = (stitch_count × stitch_width) / π`. The resulting array of diameters is the training label for that part.

#### Scenario: Sphere profile reconstructed
- **WHEN** a pattern part has rounds with stitch counts [6, 12, 18, 24, 24, 24, 18, 12, 6]
- **THEN** the normalizer outputs a diameter array proportional to [1.9, 3.8, 5.7, 7.6, 7.6, 7.6, 5.7, 3.8, 1.9]

#### Scenario: Parts without explicit round boundaries rejected
- **WHEN** a pattern text does not separate instructions by named part (e.g., no "--- HEAD ---" separator)
- **THEN** the record is marked `parts_unclear=true` and excluded from training

---

### Requirement: Normalized records stored with provenance
Each normalized record SHALL include: source URL, source type (ravelry/amigurumitoday), pattern ID, part name, primitive type (if classifiable), stitch counts per round, reconstructed diameter profile, terminology, and a data quality score (0–1).

#### Scenario: Complete record written to dataset
- **WHEN** normalization succeeds for all parts of a pattern
- **THEN** one record per part is written to the `training_records` table with all required fields populated

#### Scenario: Partial failure isolates bad parts
- **WHEN** one part of a multi-part pattern fails normalization
- **THEN** successfully normalized parts are still written; the failed part is logged with the reason
