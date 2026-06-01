## ADDED Requirements

### Requirement: Three.js LatheGeometry renders each part as a 3D surface
The frontend SHALL load Three.js from CDN and, after a successful `/generate` response, render each part's diameter profile as a `LatheGeometry` mesh in a `<canvas>` element. The mesh SHALL be lit with a simple ambient + directional light and rendered with a soft purple material matching the site color scheme.

#### Scenario: Part rendered after generation
- **WHEN** the `/generate` response returns a list of parts with instructions
- **THEN** a rotatable 3D canvas appears for each part alongside its text instructions within 500ms of response receipt

#### Scenario: Diameter profile correctly mapped to lathe points
- **WHEN** a sphere part with diameter profile [2,4,6,8,8,8,6,4,2] is rendered
- **THEN** the lathe cross-section shows a visually spherical silhouette (wide middle, tapered ends)

---

### Requirement: 3D preview is interactively rotatable
The user SHALL be able to click-and-drag the 3D canvas to orbit the camera around the part. The canvas SHALL auto-rotate slowly when not interacting.

#### Scenario: User drags canvas to rotate
- **WHEN** the user clicks and drags on the 3D canvas
- **THEN** the camera orbits the mesh following the drag direction

#### Scenario: Auto-rotation resumes after idle
- **WHEN** the user releases the mouse and does not interact for 2 seconds
- **THEN** the mesh resumes slow auto-rotation on the Y axis

---

### Requirement: Parts are composited in a combined scene
The frontend SHALL display a combined 3D scene showing all parts spatially arranged, with the body at center, head above it, limbs to the sides, and accessories at their typical positions. Positions SHALL use heuristic offsets based on part name keywords (head, body, arm, leg, ear, tail).

#### Scenario: Head placed above body
- **WHEN** parts include one named "Head" and one named "Body"
- **THEN** the Head mesh is positioned directly above the Body mesh with a small gap in the combined scene

#### Scenario: Unknown parts placed in a row
- **WHEN** a part name does not match any spatial heuristic keyword
- **THEN** it is placed to the right of the previous unpositioned part in the combined scene

---

### Requirement: 3D preview degrades gracefully
If Three.js fails to load (e.g., CDN unavailable or WebGL unsupported), the frontend SHALL display the text instructions normally without any error affecting the instruction display.

#### Scenario: WebGL not supported
- **WHEN** the user's browser does not support WebGL
- **THEN** the canvas is replaced with a static note "3D preview not available in this browser" and the text instructions are unaffected
