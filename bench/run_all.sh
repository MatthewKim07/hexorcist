#!/usr/bin/env bash
# Benchmark v2, steps 1-2: rebuild the stack, check it, then run all three legs serially.
#
#   bench/run_all.sh                 start a new run (or resume the one recorded in bench/results/.run_id)
#   RUN_ID=my_id bench/run_all.sh    force a run id
#   KEEP_BENCH_LIMITS=1 bench/run_all.sh   leave the raised rate limit in place when the script ends
#
# Legs (each case once, serial):
#   1. baseline, DeepSeek (LLM_* env)
#   2. baseline, gpt-4o-mini (OPENAI_* env)
#   3. Hexorcist through the live API, DeepSeek
#
# Caps: DeepSeek 0.80 USD (baseline + Hexorcist together), OpenAI 3.00 USD. A cap stops the run cleanly (exit 3).
# Resume: baseline calls are cached under bench/cache/, finished Hexorcist cases are kept as one file each.
# Progress goes to bench/results/run.log. This script never reads or prints .env (the Python runners load it themselves).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/backend/.venv/bin/python"
RESULTS="$ROOT/bench/results"
LOG="$RESULTS/run.log"
PORT="${HEXORCIST_PORT:-8080}"
API="http://127.0.0.1:${PORT}"
CAP_DS="0.80"
CAP_OAI="3.00"
FREEZE_COMMIT="6a92c57"
COMPOSE=(docker compose -f docker-compose.yml -f bench/docker-compose.bench.yml)

mkdir -p "$RESULTS"

# Keep the Mac awake for the whole run (about 2 hours).
if command -v caffeinate >/dev/null; then caffeinate -i -w $$ & fi

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }
die() { log "ABORT: $*"; exit "${2:-1}"; }

# Run a command, copy its output to the log, return its exit status.
run_logged()
{
  "$@" 2>&1 | tee -a "$LOG"
  return "${PIPESTATUS[0]}"
}

# Sum of cost_usd over the rows of a result file (0 if the file is missing).
cost_of()
{
  "$PY" - "$1" <<'EOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file():
    print(0.0)
else:
    d = json.loads(p.read_text())
    print(round(sum(float(c.get("cost_usd") or 0) for c in d.get("cases", [])), 6))
EOF
}

# A baseline result is final when it finished without a budget stop and without error rows.
baseline_done()
{
  "$PY" - "$1" <<'EOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file():
    sys.exit(1)
d = json.loads(p.read_text())
rows = d.get("cases", [])
ok = not d.get("stopped") and rows and not any(r.get("error") for r in rows)
sys.exit(0 if ok else 1)
EOF
}

# --- Run id (resume-friendly) ---------------------------------------------------------------------
if [ -n "${RUN_ID:-}" ]; then
  :
elif [ -s "$RESULTS/.run_id" ]; then
  RUN_ID="$(cat "$RESULTS/.run_id")"
else
  RUN_ID="v2_full_$(date -u '+%Y%m%dT%H%M%SZ')"
fi
echo "$RUN_ID" > "$RESULTS/.run_id"

BASE_DS="$RESULTS/${RUN_ID}_baseline_deepseek.json"
BASE_OAI="$RESULTS/${RUN_ID}_baseline_openai.json"
HEX_OUT="$RESULTS/${RUN_ID}_hexorcist.json"
HEX_DIR="$RESULTS/${RUN_ID}_hexorcist_cases"
mkdir -p "$HEX_DIR"

log "=== benchmark v2 run ${RUN_ID} ==="

# --- Pre-flight (no stack needed yet) -------------------------------------------------------------
[ -x "$PY" ] || die "backend venv missing at $PY"
command -v docker >/dev/null || die "docker not on PATH"
command -v curl >/dev/null || die "curl not on PATH"

# Frozen cases must be identical to the freeze commit.
if [ -n "$(git diff --stat "$FREEZE_COMMIT" HEAD -- bench/cases)" ] || [ -n "$(git status --short bench/cases)" ]; then
  die "bench/cases differs from freeze commit ${FREEZE_COMMIT}. Cases are frozen."
fi
log "freeze check ok: bench/cases unchanged since ${FREEZE_COMMIT}"

# Endpoint check. Prints only model names and hosts, never keys.
"$PY" - <<'EOF' 2>&1 | tee -a "$LOG"
import sys
from pathlib import Path
from urllib.parse import urlparse
root = Path.cwd()
sys.path[:0] = [str(root), str(root / "backend")]
from dotenv import load_dotenv
load_dotenv(root / ".env", override=False)
from bench.llm_budget import endpoint_from_env
bad = []
ds = endpoint_from_env("LLM")
oai = endpoint_from_env("OPENAI")
print(f"preflight LLM_*    : configured={ds.configured} model={ds.model} host={urlparse(ds.base_url).hostname}")
print(f"preflight OPENAI_* : configured={oai.configured} model={oai.model} host={urlparse(oai.base_url).hostname}")
if not ds.configured or ds.model != "deepseek-chat" or "deepseek" not in (urlparse(ds.base_url).hostname or ""):
    bad.append("LLM_* must be deepseek-chat on a deepseek host")
if not oai.configured or oai.model != "gpt-4o-mini" or "openai.com" not in (urlparse(oai.base_url).hostname or ""):
    bad.append("OPENAI_* must be gpt-4o-mini on api.openai.com")
if bad:
    print("PREFLIGHT FAIL: " + "; ".join(bad))
    sys.exit(1)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || die "endpoint pre-flight failed (see above)"

# --- Step 1: rebuild + health ---------------------------------------------------------------------
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

log "step 1: docker compose up --build -d (with bench override: RATE_LIMIT_PER_HOUR=1000)"
run_logged "${COMPOSE[@]}" up --build -d || die "docker compose up failed"

HEALTH=""
for _ in $(seq 1 60); do
  HEALTH="$(curl -fs -m 5 "$API/api/health" 2>/dev/null || true)"
  [ -n "$HEALTH" ] && break
  sleep 2
done
[ -n "$HEALTH" ] || die "no answer from $API/api/health after 120 s"

# Parse health with Python; print only non-secret fields.
HEALTH_JSON="$HEALTH" "$PY" - <<'EOF' 2>&1 | tee -a "$LOG"
import json, os, sys
h = json.loads(os.environ["HEALTH_JSON"])
lim = h.get("limits", {})
print(f"health: ok={h.get('ok')} sandbox={h.get('sandbox')} llm_model={h.get('llm_model')} "
      f"llm_base_url={h.get('llm_base_url')} passcode_required={h.get('passcode_required')} "
      f"rate_limit_per_hour={lim.get('rate_limit_per_hour')} max_active_runs={lim.get('max_active_runs')}")
errs = []
if not h.get("ok"):
    errs.append("health not ok")
if not h.get("llm_configured") or h.get("llm_model") != "deepseek-chat":
    errs.append(f"app model is {h.get('llm_model')!r}, need deepseek-chat")
if lim.get("rate_limit_per_hour", 0) < 100:
    errs.append("rate limit override not applied (need >= 100/hour)")
if h.get("passcode_required") and not os.environ.get("DEMO_PASSCODE"):
    errs.append("passcode required but DEMO_PASSCODE is not set in this shell")
if errs:
    print("PREFLIGHT FAIL: " + "; ".join(errs))
    sys.exit(1)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || die "health pre-flight failed (see above)"
log "step 1 done: stack current, app on deepseek-chat"

# --- Step 2, legs 1 and 2: baselines --------------------------------------------------------------
# run_baseline writes RESULTS_DIR/<run-id>.json, so pass the run id without the extension.
# Step 2, legs 1 and 2 (baselines).
baseline_leg()
{
  local label="$1" endpoint="$2" out="$3" runid
  runid="$(basename "$out" .json)"
  if baseline_done "$out"; then
    log "leg ${label}: already complete (${out##*/}), skipping"
    return 0
  fi
  log "leg ${label}: starting (cached calls cost nothing on a resume)"
  run_logged "$PY" -m bench.run_baseline --endpoint "$endpoint" \
    --max-cost-deepseek "$CAP_DS" --max-cost-openai "$CAP_OAI" --run-id "$runid"
  local rc=$?
  [ "$rc" -eq 0 ] || die "leg ${label}: runner exited with status ${rc}"
  [ -f "$out" ] || die "leg ${label}: no result file written"
  local stopped
  stopped="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("stopped") or "")' "$out")"
  if [ -n "$stopped" ]; then
    log "BUDGET STOP in leg ${label}: ${stopped}"
    log "partial results kept in ${out##*/}. Raise the cap or accept partial scoring, then rerun to resume."
    exit 3
  fi
  local n err
  n="$("$PY" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["cases"]))' "$out")"
  err="$("$PY" -c 'import json,sys; print(sum(1 for r in json.load(open(sys.argv[1]))["cases"] if r.get("error")))' "$out")"
  log "leg ${label}: done, ${n} cases, ${err} errors, cost \$$(cost_of "$out")"
  [ "$err" -eq 0 ] || log "WARN: ${err} baseline case(s) errored. Rerun the script to retry only those."
}

baseline_leg "1/3 baseline deepseek" llm "$BASE_DS"
baseline_leg "2/3 baseline gpt-4o-mini" openai "$BASE_OAI"

# --- Step 2, leg 3: Hexorcist, one case at a time -------------------------------------------------
log "leg 3/3 Hexorcist (serial, one run per case, DeepSeek)"
CASES=()
while IFS= read -r line; do CASES+=("$line"); done < <("$PY" -c 'from bench.case_io import list_case_ids; print("\n".join(list_case_ids()))')
TOTAL="${#CASES[@]}"
[ "$TOTAL" -eq 40 ] || die "expected 40 cases, found ${TOTAL}"

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

# DeepSeek spend so far = baseline leg + finished Hexorcist cases. Also the largest single Hexorcist case.
ds_spent()
{
  "$PY" - "$BASE_DS" "$HEX_DIR" <<'EOF'
import json, sys
from pathlib import Path
total = 0.0
worst = 0.0
b = Path(sys.argv[1])
if b.is_file():
    total += sum(float(c.get("cost_usd") or 0) for c in json.loads(b.read_text()).get("cases", []))
for f in sorted(Path(sys.argv[2]).glob("*.json")):
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
log "baseline deepseek : \$$(cost_of "$BASE_DS")   (${BASE_DS##*/})"
log "baseline gpt-4o-mini: \$$(cost_of "$BASE_OAI")   (${BASE_OAI##*/})"
log "hexorcist deepseek: merged file ${HEX_OUT##*/}"
log "DeepSeek total (baseline + hexorcist): \$${SPENT} of cap \$${CAP_DS}"

UNFINISHED=()
for cid in "${CASES[@]}"; do
  hex_case_done "$HEX_DIR/${cid}.json" || UNFINISHED+=("$cid")
done
if [ "${#UNFINISHED[@]}" -gt 0 ]; then
  log "INCOMPLETE: ${#UNFINISHED[@]} Hexorcist case(s) not finished: ${UNFINISHED[*]}"
  log "Rerun bench/run_all.sh to resume (finished cases and cached baseline calls are not paid for again)."
  exit 3
fi
log "ALL LEGS COMPLETE for run ${RUN_ID}. Tell the agent to continue with scoring."
