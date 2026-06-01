## ADDED Requirements

### Requirement: compile_part accepts primitive_type parameter
The `compile_part` method SHALL accept an optional `primitive_type` parameter (default `"sphere"`) and use it to route to the appropriate construction method. This parameter MUST be passed through from the pattern builder in `main.py`.

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
