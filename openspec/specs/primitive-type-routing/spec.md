# primitive-type-routing Specification

## Purpose
Route `compile_part` to the correct construction method based on the part's `primitive_type`, and accept diameter arrays from either the hardcoded `GeometryEngine` path or the mesh-measurement module without distinction.

## Requirements

### Requirement: compile_part accepts primitive_type parameter
The `compile_part` method SHALL accept an optional `primitive_type` parameter (default `"sphere"`) and use it to route to the appropriate construction method. This parameter MUST be passed through from the pattern builder in `main.py`. Diameters MAY come from either the `GeometryEngine` (hardcoded geometric profile path, default) OR from the mesh-measurement module (`backend/mesh_measure.py`); the grammar accepts whichever array is passed without distinction. When the measurement module produces a valid diameter array for a part, that array REPLACES the `GeometryEngine` output for that part; when the measurement module produces no array (no bbox, mesh not ready, slicing failed), the `GeometryEngine` profile is used.

#### Scenario: Default behavior unchanged for sphere
- **WHEN** `compile_part` is called without `primitive_type` or with `primitive_type="sphere"`
- **THEN** the part SHALL use magic-ring spiral construction (existing behavior)

#### Scenario: flat_disc routed to flat construction
- **WHEN** `compile_part` is called with `primitive_type="flat_disc"`
- **THEN** the part SHALL use chain foundation + flat-row construction (see flat-disc-construction spec)

#### Scenario: All other primitives use spiral construction
- **WHEN** `compile_part` is called with any `primitive_type` other than `flat_disc`
- **THEN** the part SHALL use magic-ring spiral construction

#### Scenario: main.py passes primitive_type
- **WHEN** `main.py` calls `grammar.compile_part` for each dependency graph part
- **THEN** the `primitive_type` field from the dependency graph node SHALL be passed as the argument

#### Scenario: Measured diameters replace GeometryEngine output when available
- **WHEN** the mesh-measurement background job produces a non-empty diameter array for a part
- **THEN** the measured array is passed to `compile_part` for that part's recompilation, and the `GeometryEngine` output for that part is not used in the final swap

#### Scenario: Measured diameters absent fall back to GeometryEngine
- **WHEN** measurement is unavailable (no bbox, mesh not ready, slicing degenerate) for a part
- **THEN** the `GeometryEngine` profile for that part's `primitive_type` is used unchanged
