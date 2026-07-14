#!/usr/bin/env bash
# Serve AICrochet publicly via a Cloudflare quick tunnel.
#
# Usage: scripts/serve_public.sh
# The public URL is printed by cloudflared once the tunnel is up
# (https://<random>.trycloudflare.com — changes on every restart; for a
# stable hostname, create a named tunnel with your own domain on Cloudflare).
#
# The server binds to localhost only — the tunnel is the sole public entry.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${DEMO_PORT:-8000}"
export GENERATE_DAILY_LIMIT="${GENERATE_DAILY_LIMIT:-200}"

.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port "$PORT" &
UVICORN_PID=$!
trap 'kill "$UVICORN_PID" 2>/dev/null' EXIT

cloudflared tunnel --url "http://127.0.0.1:$PORT"
