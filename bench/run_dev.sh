#!/usr/bin/env bash
# DEV-set run: Hexorcist only (no baselines), on benchmark v2, with the current agent.
#
#   bench/run_dev.sh                                 all 40 cases
#   bench/run_dev.sh --cases solenoid_ok,loft_fan_ok a few cases (comma or space separated)
#   bench/run_dev.sh --list [--cases ...]            print what would run, then exit (touches nothing)
#   RUN_ID=my_id bench/run_dev.sh                    force a run id
#   KEEP_BENCH_LIMITS=1 bench/run_dev.sh             leave the raised rate limit in place when the script ends
#
# v2 has been seen, so these results are DEV-set results: they show the changes work, they are not final evidence.
#
# Same safeguards as run_all.sh: frozen-case check, DeepSeek endpoint pre-flight, health pre-flight, the raised rate
# limit through the bench override only (restored when the script ends), resume per case, a DeepSeek cap (0.60 USD),
# and a log in bench/results/run_dev.log. This script never reads or prints .env (the Python runners load it themselves).
# Exit 3 = budget stop or incomplete.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/backend/.venv/bin/python"
RESULTS="$ROOT/bench/results"
LOG="$RESULTS/run_dev.log"
PORT="${HEXORCIST_PORT:-8080}"
API="http://127.0.0.1:${PORT}"
CAP_DS="0.60"
FREEZE_COMMIT="6a92c57"
COMPOSE=(docker compose -f docker-compose.yml -f bench/docker-compose.bench.yml)

# --- Arguments --------------------------------------------------------------------------------------
SELECTED=()
LIST_ONLY=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cases)
      shift
      # Everything up to the next flag is a case id. Commas also separate ids.
      while [ "$#" -gt 0 ] && [[ "$1" != --* ]]; do
        IFS=',' read -r -a PARTS <<<"$1"
        for part in "${PARTS[@]}"; do
          [ -n "$part" ] && SELECTED+=("$part")
        done
        shift
      done
      [ "${#SELECTED[@]}" -gt 0 ] || { echo "--cases needs at least one case id" >&2; exit 2; }
      ;;
    --list) LIST_ONLY=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (try --help)" >&2; exit 2 ;;
  esac
done

mkdir -p "$RESULTS"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit "${2:-1}"; }

run_logged()
{
  "$@" 2>&1 | tee -a "$LOG"
  return "${PIPESTATUS[0]}"
}

[ -x "$PY" ] || { echo "backend venv missing at $PY" >&2; exit 1; }

# --- Which cases ------------------------------------------------------------------------------------
ALL=()
while IFS= read -r line; do ALL+=("$line"); done < <("$PY" -c 'from bench.case_io import list_case_ids; print("\n".join(list_case_ids()))')
[ "${#ALL[@]}" -eq 40 ] || { echo "expected 40 cases in bench/cases, found ${#ALL[@]}" >&2; exit 1; }

if [ "${#SELECTED[@]}" -gt 0 ]; then
  for cid in "${SELECTED[@]}"; do
    found=0
    for known in "${ALL[@]}"; do [ "$known" = "$cid" ] && found=1; done
    [ "$found" -eq 1 ] || { echo "unknown case id: $cid (see bench/cases/)" >&2; exit 2; }
  done
  CASES=("${SELECTED[@]}")
  KIND="smoke"
else
  CASES=("${ALL[@]}")
  KIND="full"
fi
TOTAL="${#CASES[@]}"

# --- Run id (resume-friendly, kept apart for case subsets and the full set) ----------------------------
STATE="$RESULTS/.dev_run_id_${KIND}"
if [ -n "${RUN_ID:-}" ]; then
  :
elif [ -s "$STATE" ]; then
  RUN_ID="$(cat "$STATE")"
else
  RUN_ID="dev_${KIND}_$(date -u '+%Y%m%dT%H%M%SZ')"
fi

HEX_OUT="$RESULTS/${RUN_ID}_hexorcist.json"
HEX_DIR="$RESULTS/${RUN_ID}_hexorcist_cases"

if [ "$LIST_ONLY" -eq 1 ]; then
  echo "run id : ${RUN_ID} (${KIND})"
  echo "cases  : ${TOTAL}"
  printf '  %s\n' "${CASES[@]}"
  echo "cap    : DeepSeek \$${CAP_DS}"
  echo "log    : ${LOG}"
  exit 0
fi

echo "$RUN_ID" > "$STATE"
mkdir -p "$HEX_DIR"

# Keep the Mac awake for the whole run.
if command -v caffeinate >/dev/null; then caffeinate -i -w $$ & fi

log "=== DEV-set run ${RUN_ID} (${KIND}, ${TOTAL} cases, Hexorcist only) ==="

# --- Pre-flight (no stack needed yet) -----------------------------------------------------------------
command -v docker >/dev/null || die "docker not on PATH"
command -v curl >/dev/null || die "curl not on PATH"

# Frozen cases must be identical to the freeze commit.
if [ -n "$(git diff --stat "$FREEZE_COMMIT" HEAD -- bench/cases)" ] || [ -n "$(git status --short bench/cases)" ]; then
  die "bench/cases differs from freeze commit ${FREEZE_COMMIT}. Cases are frozen."
fi
log "freeze check ok: bench/cases unchanged since ${FREEZE_COMMIT}"

# DeepSeek endpoint check. Prints only the model name and host, never a key.
"$PY" - <<'EOF' 2>&1 | tee -a "$LOG"
import sys
from pathlib import Path
from urllib.parse import urlparse
root = Path.cwd()
sys.path[:0] = [str(root), str(root / "backend")]
from dotenv import load_dotenv
load_dotenv(root / ".env", override=False)
from bench.llm_budget import endpoint_from_env
ds = endpoint_from_env("LLM")
print(f"preflight LLM_*: configured={ds.configured} model={ds.model} host={urlparse(ds.base_url).hostname}")
if not ds.configured or ds.model != "deepseek-chat" or "deepseek" not in (urlparse(ds.base_url).hostname or ""):
    print("PREFLIGHT FAIL: LLM_* must be deepseek-chat on a deepseek host")
    sys.exit(1)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || die "endpoint pre-flight failed (see above)"

# --- Rebuild + health ---------------------------------------------------------------------------------
restore_limits()
{
  if [ "${KEEP_BENCH_LIMITS:-0}" = "1" ]; then
    log "KEEP_BENCH_LIMITS=1: raised rate limit left in place"
    return
  fi
  log "restoring the default rate limit (recreating backend without the bench override)"
  docker compose up -d --force-recreate backend >>"$LOG" 2>&1 || log "WARN: could not restore default backend; run: docker compose up -d --force-recreate backend"
}
trap restore_limits EXIT

log "docker compose up --build -d (bench override: RATE_LIMIT_PER_HOUR=1000). This builds the current agent code."
run_logged "${COMPOSE[@]}" up --build -d || die "docker compose up failed"

HEALTH=""
for _ in $(seq 1 60); do
  HEALTH="$(curl -fs -m 5 "$API/api/health" 2>/dev/null || true)"
  [ -n "$HEALTH" ] && break
  sleep 2
done
[ -n "$HEALTH" ] || die "no answer from $API/api/health after 120 s"

HEALTH_JSON="$HEALTH" "$PY" - <<'EOF' 2>&1 | tee -a "$LOG"
import json, os, sys
h = json.loads(os.environ["HEALTH_JSON"])
lim = h.get("limits", {})
agent = h.get("agent")
print(f"health: ok={h.get('ok')} sandbox={h.get('sandbox')} llm_model={h.get('llm_model')} "
      f"llm_base_url={h.get('llm_base_url')} passcode_required={h.get('passcode_required')} "
      f"rate_limit_per_hour={lim.get('rate_limit_per_hour')} max_active_runs={lim.get('max_active_runs')}")
print(f"agent settings: {agent}")
errs = []
if not h.get("ok"):
    errs.append("health not ok")
if not h.get("llm_configured") or h.get("llm_model") != "deepseek-chat":
    errs.append(f"app model is {h.get('llm_model')!r}, need deepseek-chat")
if lim.get("rate_limit_per_hour", 0) < 100:
    errs.append("rate limit override not applied (need >= 100/hour)")
if not agent:
    errs.append("the running backend is not the current agent (no 'agent' settings in /api/health): the rebuild did not take")
elif not agent.get("cross_check") or not agent.get("search_variants"):
    errs.append(f"cross-check or search is off in this stack: {agent}")
if h.get("passcode_required") and not os.environ.get("DEMO_PASSCODE"):
    errs.append("passcode required but DEMO_PASSCODE is not set in this shell")
if errs:
    print("PREFLIGHT FAIL: " + "; ".join(errs))
    sys.exit(1)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || die "health pre-flight failed (see above)"
log "stack current, app on deepseek-chat"

# --- Hexorcist, one case at a time --------------------------------------------------------------------
hex_case_done()
{
  "$PY" - "$1" <<'EOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file():
    sys.exit(1)
rows = json.loads(p.read_text()).get("cases", [])
sys.exit(0 if rows and not rows[0].get("error") and rows[0].get("status") else 1)
EOF
}

# DeepSeek spend so far (finished cases of this run) and the largest single case.
ds_spent()
{
  "$PY" - "$HEX_DIR" <<'EOF'
import json, sys
from pathlib import Path
total = 0.0
worst = 0.0
for f in sorted(Path(sys.argv[1]).glob("*.json")):
    for c in json.loads(f.read_text()).get("cases", []):
        v = float(c.get("cost_usd") or 0)
        total += v
        worst = max(worst, v)
print(f"{total:.6f} {worst:.6f}")
EOF
}

IDX=0
ERR_STREAK=0
for cid in "${CASES[@]}"; do
  IDX=$((IDX + 1))
  CASE_FILE="$HEX_DIR/${cid}.json"
  if hex_case_done "$CASE_FILE"; then
    log "hexorcist ${IDX}/${TOTAL} ${cid}: already done, skipping"
    continue
  fi

  read -r SPENT WORST <<<"$(ds_spent)"
  # Stop before a case that could push DeepSeek spend over the cap. Use the largest case so far, at least 0.02.
  NEXT="$("$PY" -c 'import sys; print(max(float(sys.argv[1]), 0.02))' "$WORST")"
  if "$PY" -c 'import sys; sys.exit(0 if float(sys.argv[1]) + float(sys.argv[2]) > float(sys.argv[3]) else 1)' "$SPENT" "$NEXT" "$CAP_DS"; then
    log "BUDGET STOP before hexorcist case ${IDX}/${TOTAL} (${cid}): DeepSeek spent \$${SPENT}, next case may cost up to \$${NEXT}, cap \$${CAP_DS}"
    break
  fi

  log "hexorcist ${IDX}/${TOTAL} ${cid}: start (DeepSeek spent so far \$${SPENT})"
  run_logged "$PY" -m bench.run_hexorcist --api "$API" --run-id "${RUN_ID}_hexorcist_cases/${cid}" "$cid"
  rc=$?
  if [ "$rc" -ne 0 ] || ! hex_case_done "$CASE_FILE"; then
    ERR_STREAK=$((ERR_STREAK + 1))
    log "hexorcist ${IDX}/${TOTAL} ${cid}: FAILED (exit ${rc}, errored row). It will be retried on resume."
    if [ "$ERR_STREAK" -ge 3 ]; then
      die "3 failures in a row. Check the stack (${COMPOSE[*]} logs backend) and rerun to resume." 2
    fi
  else
    ERR_STREAK=0
    log "hexorcist ${IDX}/${TOTAL} ${cid}: done"
  fi
  sleep 2
done

# Merge finished per-case files into one result file, in case order.
"$PY" - "$HEX_DIR" "$HEX_OUT" "$API" "$RUN_ID" "${CASES[@]}" <<'EOF' 2>&1 | tee -a "$LOG"
import json, sys
from pathlib import Path
hex_dir, out, api, run_id, *cases = sys.argv[1:]
rows = []
missing = []
for cid in cases:
    f = Path(hex_dir) / f"{cid}.json"
    if not f.is_file():
        missing.append(cid)
        continue
    rows.extend(json.loads(f.read_text()).get("cases", []))
Path(out).write_text(json.dumps({"run_id": f"{run_id}_hexorcist", "system": "hexorcist", "api": api, "missing": missing, "cases": rows}, indent=2) + "\n")
errs = [r["case_id"] for r in rows if r.get("error")]
print(f"merged {len(rows)} hexorcist rows into {out}; missing={missing}; errored={errs}")
EOF

read -r SPENT WORST <<<"$(ds_spent)"
log "=== summary ==="
log "hexorcist deepseek: merged file ${HEX_OUT##*/}"
log "DeepSeek total: \$${SPENT} of cap \$${CAP_DS}"

UNFINISHED=()
for cid in "${CASES[@]}"; do
  hex_case_done "$HEX_DIR/${cid}.json" || UNFINISHED+=("$cid")
done
if [ "${#UNFINISHED[@]}" -gt 0 ]; then
  log "INCOMPLETE: ${#UNFINISHED[@]} case(s) not finished: ${UNFINISHED[*]}"
  log "Rerun the same command to resume (finished cases are not paid for again)."
  exit 3
fi
log "ALL CASES COMPLETE for run ${RUN_ID}. Tell the agent to continue with scoring and comparison."
