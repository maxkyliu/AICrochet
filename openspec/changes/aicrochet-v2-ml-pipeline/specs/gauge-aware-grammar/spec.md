## ADDED Requirements

### Requirement: Gauge input accepted in /generate request
The `/generate` endpoint SHALL accept optional `gauge_stitches_per_10cm` (float) and `gauge_rows_per_10cm` (float) fields in a multipart or JSON body alongside the image file. When provided, these values SHALL override the default `stitch_width=1.0` and `stitch_height=1.0` in `CrochetGrammar`.

#### Scenario: Gauge provided and applied
- **WHEN** a `/generate` request includes `gauge_stitches_per_10cm=20` and `gauge_rows_per_10cm=24`
- **THEN** `stitch_width` is set to `10/20 = 0.5 cm` and `stitch_height` to `10/24 ≈ 0.417 cm` for that request

#### Scenario: No gauge provided uses defaults
- **WHEN** a `/generate` request does not include gauge fields
- **THEN** `CrochetGrammar` uses `stitch_width=1.0` and `stitch_height=1.0` as before

---

### Requirement: Stitch count computed from physical gauge
When gauge is provided, `CrochetGrammar.compile_part()` SHALL compute stitch counts using `count = max(6, 6 × round((diameter × π / stitch_width_cm) / 6))` where `stitch_width_cm` is derived from the gauge input, producing counts that correspond to physical centimeter dimensions.

#### Scenario: Gauge-derived counts differ from default
- **WHEN** gauge_stitches_per_10cm=20 (stitch_width=0.5cm) and diameter=8 units (8cm)
- **THEN** stitch count = 6 × round((8 × π / 0.5) / 6) = 6 × round(8.38) = 6 × 8 = 48 stitches per round

#### Scenario: Counts always snap to multiple of 6
- **WHEN** the raw stitch count calculation produces a non-multiple of 6
- **THEN** it is rounded to the nearest multiple of 6 and never falls below 6

---

### Requirement: Gauge input available in frontend UI
The frontend SHALL include a collapsible "Gauge Settings" panel with two numeric inputs (stitches per 10cm, rows per 10cm) and a preset dropdown with common yarn weights (Fingering: 28/36, Sport: 24/32, DK: 22/28, Worsted: 20/24, Bulky: 14/18). Selecting a preset SHALL populate the input fields. The gauge values SHALL be sent with the `/generate` form submission.

#### Scenario: Preset populates fields
- **WHEN** the user selects "Worsted" from the gauge preset dropdown
- **THEN** the stitches field is set to 20 and the rows field is set to 24 automatically

#### Scenario: Custom gauge overrides preset
- **WHEN** the user selects a preset then manually edits a field
- **THEN** the manually edited value is used in the request (preset does not re-override)

#### Scenario: Gauge panel is collapsed by default
- **WHEN** the page first loads
- **THEN** the gauge settings panel is collapsed and not visible, keeping the UI minimal for casual users
