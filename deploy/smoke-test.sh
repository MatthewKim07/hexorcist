#!/usr/bin/env bash
# Prove a deployed stack works end to end, and save the evidence. Run from anywhere on the VM.
# Usage: deploy/smoke-test.sh [--skip-presets]
set -uo pipefail
cd "$(dirname "$0")/.."

RESULTS="smoke-results-$(date -u +%Y%m%dT%H%M%SZ).txt"
exec > >(tee "$RESULTS") 2>&1

failures=0
pass() { echo "  PASS $1"; }
fail() { echo "  FAIL $1"; failures=$((failures + 1)); }

# Tools run in a throwaway backend container. It already has the Docker socket and .env, and the
# image only ships app/, so the scripts are mounted read-only for this one command.
tool() {
    deploy/compose.sh run --rm --no-deps -T \
        -v "$PWD/backend/scripts:/srv/scripts:ro" \
        -v "$PWD/backend/tests:/srv/tests:ro" \
        -v "$PWD/sandbox/examples:/sandbox/examples:ro" \
        backend python -m "$@"
}

host="$(deploy/compose.sh host)"
url="https://$host"
# The tools run in a container. Override this if the VM cannot reach its own public address.
api="${SMOKE_API:-$url}"
echo "Smoke test of $url at $(git log --oneline -1)"
echo "VM: $(nproc 2>/dev/null) vCPU, $(free -g 2>/dev/null | awk '/Mem:/ {print $2}') GB RAM, $(uname -m), $(df -h / | awk 'NR==2 {print $4}') free"

echo
echo "== 1. HTTPS and health"
health=""
for _ in $(seq 1 40); do
    health="$(curl -fsS -m 10 "$url/api/health" 2>/dev/null)" && break
    sleep 5
done
if [ -z "$health" ]; then
    fail "$url/api/health did not answer over valid HTTPS within 200 s"
    deploy/compose.sh logs --tail 30 caddy
    exit 1
fi
pass "/api/health answers over HTTPS with a certificate curl trusts"
echo "  certificate issuer: $(echo | openssl s_client -connect "$host:443" -servername "$host" 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null)"
echo "$health" | python3 -c '
import json, sys
h = json.load(sys.stdin)
print("  model", h["llm_model"], "at", h["llm_base_url"])
checks = [
    ("Docker reachable and sandbox image present", h["ok"]),
    ("LLM key configured", h["llm_configured"]),
    ("LLM model set", bool(h["llm_model"])),
    ("using Vultr Serverless Inference", "vultrinference" in h["llm_base_url"]),
    ("passcode required", h["passcode_required"]),
    ("rate limit on", h["limits"].get("rate_limit_per_hour", 0) > 0),
]
for label, ok in checks:
    print("  " + ("PASS " if ok else "FAIL ") + label)
sys.exit(0 if all(ok for _, ok in checks) else 1)
' || failures=$((failures + 1))

echo
echo "== 2. Public surface"
code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' "http://$host/")"
if [ "$code" = 308 ] || [ "$code" = 301 ]; then pass "HTTP redirects to HTTPS ($code)"; else fail "HTTP answered $code instead of redirecting"; fi
code="$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"mode":"build","description":"x"}' "$url/api/runs")"
if [ "$code" = 401 ]; then pass "starting a run without the passcode is refused"; else fail "starting a run without the passcode answered $code"; fi
if command -v ss >/dev/null; then
    listening="$(ss -H -tln | awk '{print $4}' | sed 's/.*://' | sort -un | tr '\n' ' ')"
    echo "  listening TCP ports: $listening"
    bad_ports="$(ss -H -tln | awk '{print $4}' | grep -Ev '^(127\.|\[::1\]|\[?::ffff:127)' | sed 's/.*://' | sort -un | grep -Ev '^(22|80|443)$' | tr '\n' ' ')"
    if [ -z "$bad_ports" ]; then pass "only 22, 80 and 443 listen on public addresses"; else fail "also listening publicly: $bad_ports"; fi
else
    fail "cannot check open ports: ss is not installed"
fi
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    extra="$(ufw status | awk '/ALLOW/ {print $1}' | grep -Ev '^(22|80|443)(/tcp)?$' | tr '\n' ' ')"
    if [ -z "$extra" ]; then pass "ufw active, allowing only 22, 80 and 443"; else fail "ufw also allows: $extra"; fi
else
    fail "ufw is not active"
fi
holders="$(docker ps --no-trunc --format '{{.Names}} {{.Mounts}}' | grep -E 'docker[^,]*\.sock' | awk '{print $1}' | tr '\n' ' ')"
echo "  containers holding the Docker socket: $holders"
if [ "$(echo "$holders" | wc -w | tr -d ' ')" = 1 ] && [[ "$holders" == *backend* ]]; then
    pass "only the backend holds the Docker socket"
else
    fail "expected only the backend to hold the Docker socket, found: $holders"
fi

echo
echo "== 3. Sandbox lockdown on this kernel"
verify_log="$(mktemp)"
if tool scripts.verify_sandbox > "$verify_log" 2>&1; then
    grep -E 'PASS|ALL STEP 0' "$verify_log"
    pass "verify_sandbox"
else
    tail -30 "$verify_log"
    fail "verify_sandbox"
fi
rm -f "$verify_log"

echo
echo "== 4. Emulation speed on this VM"
tool scripts.measure_speed || fail "measure_speed"

echo
echo "== 5. Containment preset, through the public URL"
tool scripts.run_presets --api "$api" --quiet containment || fail "containment preset"

if [ "${1:-}" != "--skip-presets" ]; then
    echo
    echo "== 6. All presets, with the real model, through the public URL"
    tool scripts.run_presets --api "$api" --quiet --repeat 1 || fail "run_presets"
fi

echo
echo "Saved to $RESULTS"
if [ "$failures" = 0 ]; then
    echo "SMOKE TEST PASSED"
else
    echo "SMOKE TEST: $failures FAILURE(S)"
    exit 1
fi
