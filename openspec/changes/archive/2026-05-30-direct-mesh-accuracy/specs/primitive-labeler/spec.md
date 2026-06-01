## MODIFIED Requirements

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
