#!/usr/bin/env bash
# Build the two external GPL-3.0 CLI tools AICrochet drives as subprocesses:
#   - graph_standalone   (CrochetPARADE)          : pattern stitch-graph -> 3D coordinates
#   - crochet_remesh     (CrochetPARADE_Remesher) : STL mesh -> seamless crochet pattern
#
# Both are invoked arm's-length (subprocess only); AICrochet does not link or
# embed their source. graph_standalone requires a minimal stdin patch (its
# stdin read is commented out upstream). This script clones, patches, builds,
# and records provenance for GPL compliance.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$ROOT/.external_tools"
mkdir -p "$TOOLS_DIR"

GRAPH_REPO="https://codeberg.org/crochetparade/CrochetPARADE.git"
REMESH_REPO="https://codeberg.org/crochetparade/CrochetPARADE_Remesher.git"
GRAPH_DIR="$TOOLS_DIR/CrochetPARADE"
REMESH_DIR="$TOOLS_DIR/CrochetPARADE_Remesher"

clone_or_update() {
  local repo="$1" dir="$2"
  if [ -d "$dir/.git" ]; then
    echo "Updating $(basename "$dir")..."
    git -C "$dir" pull --ff-only || echo "  (pull skipped; using existing checkout)"
  else
    echo "Cloning $(basename "$dir")..."
    git clone --depth 1 "$repo" "$dir"
  fi
}

# ── graph_standalone (C++) ────────────────────────────────────────────────────
clone_or_update "$GRAPH_REPO" "$GRAPH_DIR"

echo "Applying stdin patch to graph_standalone.cpp..."
python3 - "$GRAPH_DIR/graph_standalone.cpp" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = "    std::string dotContent(jsInput);"
new = ("    std::stringstream _cp_stdin; _cp_stdin << std::cin.rdbuf();\n"
       "    std::string dotContent = _cp_stdin.str();\n"
       "    if (dotContent.empty()) dotContent = jsInput;  // AICrochet stdin patch")
if "AICrochet stdin patch" in s:
    print("  already patched.")
elif s.count(old) == 1:
    open(p, "w").write(s.replace(old, new))
    print("  patched: graph_standalone now reads its graph from stdin.")
else:
    sys.exit(f"  ERROR: expected exactly one occurrence of the dotContent line, found {s.count(old)}")
PY

echo "Building graph_standalone (g++ -O2)..."
g++ -O2 -o "$GRAPH_DIR/graph_standalone" "$GRAPH_DIR/graph_standalone.cpp"
GRAPH_BIN="$GRAPH_DIR/graph_standalone"

# ── crochet_remesh (Rust) ─────────────────────────────────────────────────────
clone_or_update "$REMESH_REPO" "$REMESH_DIR"

echo "Building crochet_remesh (cargo build --release)..."
( cd "$REMESH_DIR" && cargo build --release )
# Binary name may be the package name; resolve it from target/release.
REMESH_BIN="$(find "$REMESH_DIR/target/release" -maxdepth 1 -type f -name 'crochet_remesh' -o -maxdepth 1 -type f -name 'crochet*remesh*' 2>/dev/null | grep -v '\.d$' | head -1)"

# ── Provenance record (GPL compliance) ────────────────────────────────────────
cat > "$TOOLS_DIR/PROVENANCE.md" <<EOF
# External GPL Tool Provenance

These tools are built from upstream source and invoked by AICrochet as
arm's-length subprocesses. They remain under GPL-3.0-or-later. AICrochet does
not link or embed their source.

## graph_standalone (CrochetPARADE)
- Source: $GRAPH_REPO
- License: GPL-3.0-or-later (see $GRAPH_DIR/README.md)
- LOCAL MODIFICATION: a stdin patch is applied to graph_standalone.cpp so the
  compiled binary reads its stitch-graph from standard input instead of the
  upstream hardcoded demo. The modified source is at
  $GRAPH_DIR/graph_standalone.cpp and must be offered alongside any distribution
  of the patched binary per GPL.

## crochet_remesh (CrochetPARADE_Remesher)
- Source: $REMESH_REPO
- License: GPL-3.0-or-later (see $REMESH_DIR/README.md)
- Unmodified.
EOF

echo ""
echo "── Done ──────────────────────────────────────────────────────────────────"
echo "GRAPH_STANDALONE_BIN=$GRAPH_BIN"
echo "CROCHET_REMESH_BIN=${REMESH_BIN:-<not found — check cargo build output>}"
echo "Provenance: $TOOLS_DIR/PROVENANCE.md"
echo "Set these paths in .env, or leave unset to auto-resolve under .external_tools/."
