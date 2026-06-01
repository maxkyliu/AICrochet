# primitive-labeler Specification

## Purpose
Assign a `primitive_type` to each part the LLM returns, by name matching first and a shape heuristic as fallback. Also constrains and post-processes the Gemini response to compensate for known LLM weaknesses (limb misclassification) and to add per-part bounding boxes for downstream mesh measurement.

## Requirements

### Requirement: Name-based primitive type assignment
The system SHALL assign a `primitive_type` to a normalized record by matching the record's `part_name` against a prioritized keyword list, case-insensitively.

#### Scenario: Known body-part name matches sphere
- **WHEN** `part_name` contains "HEAD", "SNOUT", or "MUZZLE"
- **THEN** `primitive_type` is set to `"sphere"`

#### Scenario: Known body-part name matches capsule
- **WHEN** `part_name` contains "BODY" or "TORSO"
- **THEN** `primitive_type` is set to `"capsule"`

#### Scenario: Known body-part name matches cylinder
- **WHEN** `part_name` contains "LEG", "ARM", "LIMB", "NECK", or "STALK"
- **THEN** `primitive_type` is set to `"cylinder"`

#### Scenario: Known body-part name matches cone
- **WHEN** `part_name` contains "TAIL", "BEAK", "HORN", "SPIKE"
- **THEN** `primitive_type` is set to `"cone"`

#### Scenario: Known body-part name matches flat_disc
- **WHEN** `part_name` contains "EAR", "WING", or "FIN"
- **THEN** `primitive_type` is set to `"flat_disc"`

#### Scenario: Known body-part name matches frustum
- **WHEN** `part_name` contains "FOOT", "BOOT", or "BASE"
- **THEN** `primitive_type` is set to `"frustum"`

#### Scenario: Known body-part name matches torus
- **WHEN** `part_name` contains "TORUS", "RING", or "COLLAR"
- **THEN** `primitive_type` is set to `"torus"`

#### Scenario: Unrecognised part name defers to shape heuristic
- **WHEN** no keyword matches `part_name`
- **THEN** `primitive_type` assignment is delegated to the shape heuristic labeler

---

### Requirement: Shape-heuristic primitive type assignment
The system SHALL assign a `primitive_type` to a record by analysing the shape of its stitch count sequence when name matching yields no result.

#### Scenario: Short sequence skips heuristic
- **WHEN** the stitch count sequence has fewer than 4 values
- **THEN** `primitive_type` remains `None` (heuristic is not applied)

#### Scenario: Non-zero floor indicates torus
- **WHEN** `min(stitch_counts) / max(stitch_counts) > 0.4`
- **THEN** `primitive_type` is set to `"torus"`

#### Scenario: Monotonically rising sequence indicates cone
- **WHEN** the stitch sequence is non-decreasing throughout
- **THEN** `primitive_type` is set to `"cone"`

#### Scenario: Symmetric rise-fall with small flat section indicates sphere
- **WHEN** rise and fall are within 20% of each other AND flat fraction < 0.3
- **THEN** `primitive_type` is set to `"sphere"`

#### Scenario: Symmetric rise-fall with moderate flat section indicates capsule
- **WHEN** rise and fall are within 20% of each other AND flat fraction is 0.3–0.6
- **THEN** `primitive_type` is set to `"capsule"`

#### Scenario: Large flat section indicates cylinder
- **WHEN** flat fraction > 0.6
- **THEN** `primitive_type` is set to `"cylinder"`

#### Scenario: Asymmetric tail indicates teardrop
- **WHEN** fall slope is more than 40% steeper than rise slope
- **THEN** `primitive_type` is set to `"teardrop"`

#### Scenario: Default fallback is frustum
- **WHEN** no other heuristic condition matches
- **THEN** `primitive_type` is set to `"frustum"`

---

### Requirement: Gemini prompt constrains limb part types
The Gemini vision prompt SHALL include an explicit rule that parts named arm, leg, paw, or flipper MUST be classified as `capsule` or `cylinder`, and never as `sphere`. The Gemini prompt SHALL additionally request a normalized 2D bounding box per part — four floats `[x_min, y_min, x_max, y_max]` in image coordinates (0..1, image-y points downward) — so downstream mesh measurement can map each part to a vertical band on the session's `.glb`. Providers other than Gemini MAY omit the bounding box; downstream consumers MUST treat the field as optional.

#### Scenario: Prompt contains limb constraint
- **WHEN** the Gemini API request is built
- **THEN** the prompt text SHALL include an explicit statement that arm/leg/paw/flipper parts use `capsule` or `cylinder`

#### Scenario: Prompt requests per-part bounding box
- **WHEN** the Gemini API request is built
- **THEN** the prompt text SHALL ask for a normalized 2D bounding box per part
- **AND** the response schema SHALL include an optional `bbox` field of four floats per part

#### Scenario: Missing bbox is tolerated downstream
- **WHEN** a vision provider returns a part without a `bbox` field
- **THEN** the part is still accepted; downstream measurement skips parts without bboxes and falls back to the hardcoded geometric profile for those parts

---

### Requirement: Server-side coercion for limb misclassification
The dependency graph builder SHALL override `sphere` classifications to `capsule` when the part name matches limb keywords, as a deterministic defense layer against Gemini prompt non-compliance.

#### Scenario: Arm classified as sphere is coerced to capsule
- **WHEN** Gemini returns `type: "sphere"` for a part whose name contains "ARM", "LEG", "PAW", or "FLIPPER"
- **THEN** the server SHALL override `type` to `"capsule"` before passing to the geometry engine

#### Scenario: Non-limb sphere classification is not changed
- **WHEN** Gemini returns `type: "sphere"` for a part whose name does not match limb keywords
- **THEN** the `type` value SHALL remain `"sphere"` unchanged

#### Scenario: Non-sphere limb classification is not changed
- **WHEN** Gemini returns `type: "capsule"` or `type: "cylinder"` for a limb part
- **THEN** the `type` value SHALL remain unchanged (coercion only applies to sphere override)
