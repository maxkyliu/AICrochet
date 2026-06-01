## ADDED Requirements

### Requirement: Scale drives diameter amplitude
The GeometryEngine SHALL multiply each diameter value in the primitive's base profile by a factor derived from the `scale` field. Scale 1.0 SHALL correspond to a maximum cross-section diameter of 8 units; scale 2.5 SHALL produce a maximum diameter of 20 units.

#### Scenario: Scale 1.0 sphere unchanged
- **WHEN** GeometryEngine processes a sphere with scale=1.0
- **THEN** the returned diameter profile matches the base sphere profile `[2,4,6,8,8,8,6,4,2]`

#### Scenario: Scale 2.5 sphere has proportionally larger diameters
- **WHEN** GeometryEngine processes a sphere with scale=2.5
- **THEN** every diameter value in the returned profile is 2.5× the base profile value

#### Scenario: Zero or negative scale is rejected
- **WHEN** GeometryEngine receives a node with scale ≤ 0
- **THEN** a ValueError is raised with a descriptive message before any profile is computed

---

### Requirement: Scale drives round count for sphere and teardrop shapes
The GeometryEngine SHALL increase the number of flat (constant-diameter) rounds at the widest point of sphere and teardrop profiles in proportion to `sqrt(scale)`, so that larger shapes are taller as well as wider.

#### Scenario: Small sphere has minimal flat rounds
- **WHEN** GeometryEngine processes a sphere with scale=1.0
- **THEN** the returned profile has exactly 3 flat rounds at the maximum diameter

#### Scenario: Large sphere has more flat rounds
- **WHEN** GeometryEngine processes a sphere with scale=4.0
- **THEN** the returned profile has at least 5 flat rounds at the maximum diameter

---

### Requirement: Scale field is passed through to grammar
The GeometryEngine SHALL include the computed `scale` value in the output part record so that `CrochetGrammar` and downstream consumers can use it for physical size calculations.

#### Scenario: Scale preserved in output record
- **WHEN** GeometryEngine processes any node with scale=1.8
- **THEN** the returned part dict contains `{"scale": 1.8}` alongside `name` and `diameters`
