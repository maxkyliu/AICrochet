## ADDED Requirements

### Requirement: Gemini prompt constrains limb part types
The Gemini vision prompt SHALL include an explicit rule that parts named arm, leg, paw, or flipper MUST be classified as `capsule` or `cylinder`, and never as `sphere`.

#### Scenario: Prompt contains limb constraint
- **WHEN** the Gemini API request is built
- **THEN** the prompt text SHALL include an explicit statement that arm/leg/paw/flipper parts use `capsule` or `cylinder`

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
