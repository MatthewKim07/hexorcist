#!/usr/bin/env bash
# DEV-set run: Hexorcist only (no baselines), on benchmark v2, with the current agent.
#
#   bench/run_dev.sh                                 all 40 cases
#   bench/run_dev.sh --cases solenoid_ok,loft_fan_ok a few cases (comma or space separated)
#   bench/run_dev.sh --list [--cases ...]            print what would run, then exit (touches nothing)
#   bench/run_dev.sh --dir practice                  the practice set (bench/practice, 10 hidden-behaviour cases) instead of bench/cases
#   bench/run_dev.sh --search [N]                    turn the stimulus search on for this run (N variants per case, default 30)
#   RUN_ID=my_id bench/run_dev.sh                    force a run id
#   KEEP_BENCH_LIMITS=1 bench/run_dev.sh             leave the raised rate limit in place when the script ends
#
# v2 has been seen, so these results are DEV-set results: they show the changes work, they are not final evidence.
#
# Same safeguards as run_all.sh: frozen-case check, DeepSeek and OpenAI endpoint pre-flights, health pre-flight, the
# raised rate limit through the bench override only (restored when the script ends), resume per case, a DeepSeek cap
# (0.60 USD) and an OpenAI cap (0.50 USD, for clean room 2), and a log in bench/results/run_dev.log.
# Clean room 1 is written by DeepSeek, clean room 2 by the OPENAI_* model (gpt-4o-mini). The stimulus search is OFF unless
# --search is given. It is switched on through the bench override (BENCH_SEARCH_VARIANTS), so .env is never touched, and it
# keeps a finding only if it passes its three acceptance gates. The practice set is for tuning: it is not frozen, so --dir
# practice skips the freeze check and only reports the set's fingerprint.
# ALLOW_FALLBACK=1 lets the run go ahead with two DeepSeek rooms when OPENAI_* is not configured (the report says so).
# This script never reads or prints .env (the Python runners load it themselves).
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
CAP_OA="0.50"
FREEZE_COMMIT="6a92c57"
COMPOSE=(docker compose -f docker-compose.yml -f bench/docker-compose.bench.yml)

# --- Arguments --------------------------------------------------------------------------------------
SELECTED=()
LIST_ONLY=0
CASE_DIR="frozen"
SEARCH_N=0
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
    --dir)
      [ "$#" -ge 2 ] || { echo "--dir needs practice, frozen or a path" >&2; exit 2; }
      CASE_DIR="$2"; shift 2 ;;
    --search)
      SEARCH_N=30
      shift
      if [ "$#" -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then SEARCH_N="$1"; shift; fi
      [ "$SEARCH_N" -ge 1 ] && [ "$SEARCH_N" -le 100 ] || { echo "--search takes 1 to 100 variants" >&2; exit 2; } ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
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
while IFS= read -r line; do ALL+=("$line"); done < <("$PY" -c 'import sys; from bench.case_io import list_case_ids, use_cases_dir; use_cases_dir(sys.argv[1]); print("\n".join(list_case_ids()))' "$CASE_DIR")
FROZEN=0
case "$CASE_DIR" in frozen|cases|bench/cases|bench/cases/) FROZEN=1 ;; esac
if [ "$FROZEN" -eq 1 ]; then
  [ "${#ALL[@]}" -eq 40 ] || { echo "expected 40 cases in bench/cases, found ${#ALL[@]}" >&2; exit 1; }
else
  [ "${#ALL[@]}" -gt 0 ] || { echo "no cases found in ${CASE_DIR}" >&2; exit 1; }
fi

if [ "${#SELECTED[@]}" -gt 0 ]; then
  for cid in "${SELECTED[@]}"; do
    found=0
    for known in "${ALL[@]}"; do [ "$known" = "$cid" ] && found=1; done
    [ "$found" -eq 1 ] || { echo "unknown case id: $cid (known: ${ALL[*]})" >&2; exit 2; }
  done
  CASES=("${SELECTED[@]}")
  KIND="smoke"
else
  CASES=("${ALL[@]}")
  KIND="full"
fi
if [ "$FROZEN" -eq 0 ]; then
  KIND="${CASE_DIR##*/}_${KIND}"
fi
if [ "$SEARCH_N" -gt 0 ]; then
  KIND="${KIND}_search"
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
  echo "cases  : ${TOTAL} from ${CASE_DIR}"
  echo "search : $([ "$SEARCH_N" -gt 0 ] && echo "ON, ${SEARCH_N} variants per case, three acceptance gates" || echo off)"
  printf '  %s\n' "${CASES[@]}"
  echo "cap    : DeepSeek \$${CAP_DS}, OpenAI \$${CAP_OA}"
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

# Frozen cases must be identical to the freeze commit. The practice set is not frozen: only its fingerprint is reported.
if [ "$FROZEN" -eq 1 ]; then
  if [ -n "$(git diff --stat "$FREEZE_COMMIT" HEAD -- bench/cases)" ] || [ -n "$(git status --short bench/cases)" ]; then
    die "bench/cases differs from freeze commit ${FREEZE_COMMIT}. Cases are frozen."
  fi
  log "freeze check ok: bench/cases unchanged since ${FREEZE_COMMIT}"
else
  log "case set: ${CASE_DIR} (not frozen, for tuning). $("$PY" bench/freeze_hash.py --dir "$CASE_DIR" 2>&1 | head -1)"
fi
log "stimulus search: $([ "$SEARCH_N" -gt 0 ] && echo "ON with ${SEARCH_N} variants per case (three acceptance gates)" || echo off)"

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

# OpenAI endpoint check for clean room 2. Prints only the model name and host, never a key.
ALLOW_FALLBACK="${ALLOW_FALLBACK:-0}" "$PY" - <<'EOF' 2>&1 | tee -a "$LOG"
import os, sys
from pathlib import Path
from urllib.parse import urlparse
root = Path.cwd()
sys.path[:0] = [str(root), str(root / "backend")]
from dotenv import load_dotenv
load_dotenv(root / ".env", override=False)
from bench.llm_budget import endpoint_from_env
oa = endpoint_from_env("OPENAI")
print(f"preflight OPENAI_*: configured={oa.configured} model={oa.model} host={urlparse(oa.base_url).hostname}")
if not oa.configured or oa.model != "gpt-4o-mini" or "openai" not in (urlparse(oa.base_url).hostname or ""):
    if os.environ.get("ALLOW_FALLBACK") == "1":
        print("PREFLIGHT NOTE: OPENAI_* is not configured for gpt-4o-mini. ALLOW_FALLBACK=1, so both clean rooms will use DeepSeek and the report will say so.")
    else:
        print("PREFLIGHT FAIL: OPENAI_* must be gpt-4o-mini on an openai host for the mixed-model rooms (ALLOW_FALLBACK=1 runs two DeepSeek rooms instead)")
        sys.exit(1)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || die "OpenAI pre-flight failed (see above)"

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

export BENCH_SEARCH_VARIANTS="$SEARCH_N"
log "docker compose up --build -d (bench override: RATE_LIMIT_PER_HOUR=1000, SEARCH_VARIANTS=${SEARCH_N}). This builds the current agent code."
run_logged "${COMPOSE[@]}" up --build -d || die "docker compose up failed"

HEALTH=""
for _ in $(seq 1 60); do
  HEALTH="$(curl -fs -m 5 "$API/api/health" 2>/dev/null || true)"
  [ -n "$HEALTH" ] && break
  sleep 2
done
[ -n "$HEALTH" ] || die "no answer from $API/api/health after 120 s"

HEALTH_JSON="$HEALTH" ALLOW_FALLBACK="${ALLOW_FALLBACK:-0}" WANT_SEARCH="$SEARCH_N" "$PY" - <<'EOF' 2>&1 | tee -a "$LOG"
import json, os, sys
h = json.loads(os.environ["HEALTH_JSON"])
want_search = int(os.environ.get("WANT_SEARCH", "0"))
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
elif agent.get("cleanroom_samples") != 2:
    errs.append(f"this run is for two independent clean-room sketches, the stack has {agent.get('cleanroom_samples')}")
elif not agent.get("cross_check"):
    errs.append(f"the cross-check is off in this stack: {agent}")
elif (agent.get("search_variants") or 0) != want_search:
    errs.append(f"the stimulus search must be {'OFF' if not want_search else 'ON with ' + str(want_search) + ' variants'} for this run, the stack has {agent.get('search_variants')}: {agent}")
elif not (agent.get("cleanroom2") or {}).get("mixed") and os.environ.get("ALLOW_FALLBACK") != "1":
    errs.append(f"clean room 2 is not on a second model (OPENAI_* missing or CLEANROOM_MIXED=0): {agent.get('cleanroom2')}")
if h.get("passcode_required") and not os.environ.get("DEMO_PASSCODE"):
    errs.append("passcode required but DEMO_PASSCODE is not set in this shell")
if errs:
    print("PREFLIGHT FAIL: " + "; ".join(errs))
    sys.exit(1)
EOF
[ "${PIPESTATUS[0]}" -eq 0 ] || die "health pre-flight failed (see above)"
log "stack current, app on deepseek-chat, search $([ "$SEARCH_N" -gt 0 ] && echo "on (${SEARCH_N} variants)" || echo off), clean room 2 model: see agent settings above"

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

# Spend so far per provider (finished cases of this run) and the largest single case of each.
# Prints: deepseek_total deepseek_worst openai_total openai_worst
spent()
{
  "$PY" - "$HEX_DIR" <<'EOF'
import json, sys
from pathlib import Path
tot = {"ds": 0.0, "oa": 0.0}
worst = {"ds": 0.0, "oa": 0.0}
for f in sorted(Path(sys.argv[1]).glob("*.json")):
    for c in json.loads(f.read_text()).get("cases", []):
        # Older rows have one cost_usd and no split: it was all DeepSeek.
        ds = float(c["cost_deepseek_usd"] if c.get("cost_deepseek_usd") is not None else (c.get("cost_usd") or 0))
        oa = float(c.get("cost_openai_usd") or 0)
        tot["ds"] += ds; tot["oa"] += oa
        worst["ds"] = max(worst["ds"], ds); worst["oa"] = max(worst["oa"], oa)
print(f"{tot['ds']:.6f} {worst['ds']:.6f} {tot['oa']:.6f} {worst['oa']:.6f}")
EOF
}

# One line about what the cross-check did on a finished case: the room models and whether each built.
case_note()
{
  "$PY" - "$1" <<'EOF'
import json, sys
c = json.loads(open(sys.argv[1]).read())["cases"][0]
cc = c.get("cross_check") or {}
rooms = " | ".join(f"room{r.get('index')} {r.get('model')} {r.get('status')}" for r in cc.get("rooms", [])) or "no rooms"
print(f"status={c.get('status')} rule={cc.get('rule')} {rooms} left_out={len(c.get('ungrounded') or [])} cost ds=${c.get('cost_deepseek_usd')} oa=${c.get('cost_openai_usd')}")
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

  read -r SPENT WORST OA_SPENT OA_WORST <<<"$(spent)"
  # Stop before a case that could push either provider over its cap. Use the largest case so far, at least 0.02 (DeepSeek)
  # and 0.005 (OpenAI: one small clean-room sketch per case).
  NEXT="$("$PY" -c 'import sys; print(max(float(sys.argv[1]), 0.02))' "$WORST")"
  OA_NEXT="$("$PY" -c 'import sys; print(max(float(sys.argv[1]), 0.005))' "$OA_WORST")"
  if "$PY" -c 'import sys; sys.exit(0 if float(sys.argv[1]) + float(sys.argv[2]) > float(sys.argv[3]) else 1)' "$SPENT" "$NEXT" "$CAP_DS"; then
    log "BUDGET STOP before hexorcist case ${IDX}/${TOTAL} (${cid}): DeepSeek spent \$${SPENT}, next case may cost up to \$${NEXT}, cap \$${CAP_DS}"
    break
  fi
  if "$PY" -c 'import sys; sys.exit(0 if float(sys.argv[1]) + float(sys.argv[2]) > float(sys.argv[3]) else 1)' "$OA_SPENT" "$OA_NEXT" "$CAP_OA"; then
    log "BUDGET STOP before hexorcist case ${IDX}/${TOTAL} (${cid}): OpenAI spent \$${OA_SPENT}, next case may cost up to \$${OA_NEXT}, cap \$${CAP_OA}"
    break
  fi

  log "hexorcist ${IDX}/${TOTAL} ${cid}: start (spent so far: DeepSeek \$${SPENT}, OpenAI \$${OA_SPENT})"
  run_logged "$PY" -m bench.run_hexorcist --api "$API" --dir "$CASE_DIR" --run-id "${RUN_ID}_hexorcist_cases/${cid}" "$cid"
  rc=$?
  if [ "$rc" -ne 0 ] || ! hex_case_done "$CASE_FILE"; then
    ERR_STREAK=$((ERR_STREAK + 1))
    log "hexorcist ${IDX}/${TOTAL} ${cid}: FAILED (exit ${rc}, errored row). It will be retried on resume."
    if [ "$ERR_STREAK" -ge 3 ]; then
      die "3 failures in a row. Check the stack (${COMPOSE[*]} logs backend) and rerun to resume." 2
    fi
  else
    ERR_STREAK=0
    log "hexorcist ${IDX}/${TOTAL} ${cid}: done ($(case_note "$CASE_FILE"))"
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

read -r SPENT WORST OA_SPENT OA_WORST <<<"$(spent)"
log "=== summary ==="
log "hexorcist: merged file ${HEX_OUT##*/}"
log "DeepSeek total: \$${SPENT} of cap \$${CAP_DS}"
log "OpenAI total:   \$${OA_SPENT} of cap \$${CAP_OA}"

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
