## REMOVED Requirements

### Requirement: Emit a stitch-graph in the graph_standalone input format
**Reason**: The only consumer was the refinement loop, which fed the graph to `graph_standalone` for physics simulation. With the refinement loop removed and no other use of the forward renderer, the exporter is dead code.
**Migration**: `backend/dot_export.py` is deleted.

### Requirement: DOT export derives connectivity from stitch counts, not diameters
**Reason**: Same as above — no caller.
**Migration**: Removed.

### Requirement: Exported graph parses in the forward renderer
**Reason**: The forward renderer is no longer invoked.
**Migration**: Removed.
