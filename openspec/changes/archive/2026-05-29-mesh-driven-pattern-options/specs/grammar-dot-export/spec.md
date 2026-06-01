## ADDED Requirements

### Requirement: Emit a stitch-graph in the graph_standalone input format
The system SHALL provide a function that converts a part's round-by-round stitch structure into the exact text format `graph_standalone`'s `readDotFile` parses: a first line giving the embedding dimension (`3`), one quoted opaque node name per stitch (e.g. `"r0s0"`), edge lines of the form `"src" -- "dst" <length>`, and trailing param lines (`iterations=80`, `viscous_iterations=10`). Each stitch SHALL become a node; edges SHALL connect adjacent stitches within a round (closed cycle) and stitches across consecutive rounds (working edges). Edge lengths SHALL encode stitch-scale distances (uniform `1.0` to start).

#### Scenario: Output begins with the dimension line
- **WHEN** any part is exported
- **THEN** the first output line is `3` and subsequent node lines are quoted names

#### Scenario: Single round emits a cycle
- **WHEN** a round of N stitches is exported
- **THEN** the graph contains N node lines connected in a closed cycle by N intra-round `--` edge lines

#### Scenario: Increases and decreases change connectivity
- **WHEN** a round increases from N to M stitches (M > N)
- **THEN** the inter-round working edges map the N previous stitches to M current stitches such that the increased stitches share a parent, reflecting the pattern's actual stitch topology

### Requirement: DOT export derives connectivity from stitch counts, not diameters
The exporter SHALL build graph connectivity from the integer stitch counts the grammar emits per round, not from the floating-point diameter array, so that the simulated curvature reflects the real pattern rather than the geometric ideal.

#### Scenario: Connectivity matches grammar stitch counts
- **WHEN** a part is exported whose rounds have stitch counts [6, 12, 18, 18, 12, 6]
- **THEN** the graph node count equals the sum of those counts and inter-round edges follow the increase/decrease distribution the grammar used

### Requirement: Exported graph parses in the forward renderer
The emitted text SHALL conform to the format the patched `graph_standalone` accepts (stdin-fed), such that running the binary on the output produces 3D node coordinates without a parse error. The binary emits JSON lines of the form `{"name": "<id>","pos": "x,y,z"}` interleaved with progress lines; the consumer SHALL parse the JSON coordinate lines and ignore progress output.

#### Scenario: Round-trip through the renderer
- **WHEN** an exported graph for a valid part is piped to the patched `graph_standalone` over stdin
- **THEN** the binary returns a `{"name","pos"}` JSON line with x,y,z coordinates for every node and exits successfully
