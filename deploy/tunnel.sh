#!/usr/bin/env bash
# Public demo from this machine: starts the stack behind a passcode, then a Cloudflare Quick Tunnel to it.
#
#   deploy/tunnel.sh            start (or restart) the stack and the tunnel, print the URL and passcode
#
# Needs Docker, cloudflared (brew install cloudflared) and a configured .env (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).
# The URL changes every time the tunnel restarts. Stop it with Ctrl-C. This script never reads .env.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${HEXORCIST_PORT:-8080}"
PASS_FILE="deploy/.tunnel-passcode"
LOG="${TMPDIR:-/tmp}/hexorcist-tunnel.log"

command -v docker >/dev/null || { echo "Docker is not installed or not on PATH." >&2; exit 1; }
command -v cloudflared >/dev/null || { echo "cloudflared is missing. Install it with: brew install cloudflared" >&2; exit 1; }
[ -f .env ] || { echo ".env is missing. Copy .env.example to .env and fill in the LLM settings." >&2; exit 1; }

# A passcode from the environment wins. Otherwise reuse the saved one, or make a new one.
if [ -z "${DEMO_PASSCODE:-}" ]; then
  if [ ! -s "$PASS_FILE" ]; then
    (umask 077 && openssl rand -base64 18 | tr -d '/+=\n' > "$PASS_FILE")
  fi
  DEMO_PASSCODE="$(cat "$PASS_FILE")"
fi
export DEMO_PASSCODE

COMPOSE=(docker compose -f docker-compose.yml -f deploy/docker-compose.tunnel.yml)
echo "Starting the stack on 127.0.0.1:${PORT} (this builds the images the first time)..."
"${COMPOSE[@]}" up -d --build

echo -n "Waiting for the backend"
for _ in $(seq 1 60); do
  if curl -fs "http://127.0.0.1:${PORT}/api/health" 2>/dev/null | grep -q '"passcode_required":true'; then
    echo " ok"
    break
  fi
  echo -n "."
  sleep 2
done
curl -fs "http://127.0.0.1:${PORT}/api/health" | grep -q '"passcode_required":true' || { echo; echo "The backend is not up with the passcode on. Check: ${COMPOSE[*]} logs backend" >&2; exit 1; }

: > "$LOG"
cloudflared tunnel --no-autoupdate --url "http://localhost:${PORT}" > "$LOG" 2>&1 &
TUNNEL_PID=$!
trap 'kill "$TUNNEL_PID" 2>/dev/null || true' EXIT INT TERM
# Keep the Mac awake while the tunnel is up.
if command -v caffeinate >/dev/null; then caffeinate -i -w "$TUNNEL_PID" & fi

URL=""
for _ in $(seq 1 45); do
  URL="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  kill -0 "$TUNNEL_PID" 2>/dev/null || { echo "cloudflared exited. Log:" >&2; cat "$LOG" >&2; exit 1; }
  sleep 1
done
[ -n "$URL" ] || { echo "No tunnel URL after 45 s. Log: $LOG" >&2; exit 1; }

echo
echo "Public URL:  $URL"
echo "Passcode:    $DEMO_PASSCODE"
echo
echo "Share both. The passcode is only asked when someone starts a run. Ctrl-C stops the tunnel (the stack keeps running)."
wait "$TUNNEL_PID"
