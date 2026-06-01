## REMOVED Requirements

### Requirement: External GPL binaries are health-checked at startup
**Reason**: No remaining caller of either binary — `graph_standalone` is unused (refinement loop removed) and `crochet_remesh` is unused (seamless button removed). The health check would be checking for tools nothing invokes.
**Migration**: `backend/external_tools.py` is deleted; the `check_binaries()` call is removed from FastAPI startup. The binaries can stay built under `.external_tools/` (gitignored, harmless) or be deleted by the user; `scripts/build_external_tools.sh` is retained as dead/optional but no longer invoked by the app.

### Requirement: Features degrade gracefully when their binary is unavailable
**Reason**: Both dependent features are gone; nothing to degrade.
**Migration**: Removed. The `/generate` standard pattern path is unaffected by the binaries (it never depended on them) and continues to work.

### Requirement: Subprocess-only invocation preserves license separation
**Reason**: No invocations remain. AICrochet's source stays non-GPL by virtue of not calling the GPL tools at all (the stronger position than arm's-length subprocess).
**Migration**: Removed. The license note in design docs of the original mesh-driven-pattern-options change is moot in the new architecture.
