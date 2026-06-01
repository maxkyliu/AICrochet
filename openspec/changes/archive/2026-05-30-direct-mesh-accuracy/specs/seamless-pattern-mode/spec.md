## REMOVED Requirements

### Requirement: Generate a one-piece seamless pattern from the session mesh
**Reason**: The endpoint produced CrochetPARADE-DSL that crochetparade.org rejects with errors when pasted back; verified by the user with multiple manual attempts to fix. The output is unusable end-to-end.
**Migration**: The "Generate One-Piece Pattern" feature is discontinued. Users who want seamless one-piece patterns have no in-app alternative in Phase 1. The standard multi-part pattern remains the only output.

### Requirement: GLB-to-STL conversion for the remesher
**Reason**: Only consumer was the removed seamless endpoint.
**Migration**: No callers remain; `backend/seamless.py` and any STL output dir are deleted.

### Requirement: Seamless output is displayed as a distinct pattern style with framing
**Reason**: The output it framed is unusable (see first requirement); the framing header pointing at crochetparade.org no longer serves a purpose because pasted DSL fails there.
**Migration**: The "Generate One-Piece Pattern" button, the `#seamless-panel`, the framing header, and the `generateSeamless()` function are removed from the frontend.
