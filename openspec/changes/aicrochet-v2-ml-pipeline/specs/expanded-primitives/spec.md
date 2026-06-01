## ADDED Requirements

### Requirement: Eight primitive types supported
The GeometryEngine SHALL recognize and produce diameter profiles for the following primitive types: `sphere`, `cylinder`, `cone`, `frustum`, `capsule`, `teardrop`, `flat_disc`, `torus`. Unrecognized types SHALL fall back to `cylinder` and log a warning.

#### Scenario: frustum produces widening then flat profile
- **WHEN** GeometryEngine processes a node with type=`frustum`
- **THEN** the diameter profile monotonically increases then holds a flat plateau (no narrowing at the end)

#### Scenario: capsule produces rounded-end cylinder profile
- **WHEN** GeometryEngine processes a node with type=`capsule`
- **THEN** the diameter profile begins narrow, widens to a plateau, then narrows symmetrically (identical to sphere but with a longer flat middle)

#### Scenario: teardrop produces asymmetric taper
- **WHEN** GeometryEngine processes a node with type=`teardrop`
- **THEN** the diameter profile begins with a short narrow section, widens to a peak, then gradually narrows over more rounds than it widened

#### Scenario: flat_disc produces a thin wide profile
- **WHEN** GeometryEngine processes a node with type=`flat_disc`
- **THEN** the diameter profile rises steeply to max diameter and has only 1-2 flat rounds before terminating

#### Scenario: torus produces a double-taper profile
- **WHEN** GeometryEngine processes a node with type=`torus`
- **THEN** the diameter profile begins at a non-zero minimum, rises to a peak, returns to minimum, representing the outer cross-section of a ring

#### Scenario: unknown type falls back to cylinder
- **WHEN** GeometryEngine receives a node with type=`blob`
- **THEN** the returned profile is identical to cylinder and a warning is emitted to the log

---

### Requirement: Gemini prompt includes all eight primitive types
The Gemini prompt in `/generate` SHALL enumerate all eight primitive types with one-line descriptions so Gemini can classify parts accurately. The `response_schema` SHALL reflect the expanded type literal.

#### Scenario: Extended schema accepted by API
- **WHEN** a `/generate` request is made with a doll photo
- **THEN** the Gemini response schema includes all eight type literals and the API accepts it without error

#### Scenario: Gemini classifies ear as flat_disc
- **WHEN** the uploaded photo shows a doll with flat circular ears
- **THEN** at least one returned part has type=`flat_disc`
