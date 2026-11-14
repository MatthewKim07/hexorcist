# Hexorcist benchmark

Compare three things on the **same** sketches, graded by the **same** ground-truth checks:

| System | What it is |
| --- | --- |
| **A – Baseline** | Plain LLM code review: sketch + spec + pins → bug list + full patched sketch. No compiler, no emulator (`run_baseline.py`). |
| **B – Hexorcist** | Find-bugs mode through the real HTTP API (`run_hexorcist.py`). |
| **C – Ground truth** | Hand-written `checks.json` scenarios/assertions + `reference.ino` per case. |

Presets used for product tuning (`thermostat`, `button`, `logger`, `alarm`, `containment`) are **not** in this dataset.

## Freeze rule

**`bench/cases/` is frozen after the ground-truth validation commit.** Do not add, edit, or delete cases to improve scores. Do not tune Hexorcist prompts, judges, or agent loops against these cases. If a case is wrong, document it and fix in a later versioned dataset — never silently reshape the frozen set during a leaderboard run.

## Layout

```
bench/cases/<id>/
  sketch.ino      # under test (Allman braces)
  reference.ino   # known-good
  spec.md         # plain-English behaviour
  pins.json       # app PinSpec list
  truth.json      # real bugs (or [])
  checks.json     # frozen assertions + stimulus scenarios
```

## Commands

From the repo root (sandbox image required for validate/score verify):

```bash
# Re-check ground truth (no LLM)
backend/.venv/bin/python -m bench.validate

# Baseline A (uses LLM_* by default; --endpoint openai uses OPENAI_*)
backend/.venv/bin/python -m bench.run_baseline --max-cost-deepseek 0.80 --max-cost-openai 3.00 CASE_ID...

# Hexorcist B (running API; never sends truth/checks)
backend/.venv/bin/python -m bench.run_hexorcist --api http://127.0.0.1:8080 CASE_ID...

# Score A and/or B (judge uses OPENAI_* mini model)
backend/.venv/bin/python -m bench.score --baseline bench/results/….json --hexorcist bench/results/….json \
  --max-cost-deepseek 0.80 --max-cost-openai 3.00
```

LLM responses are cached under `bench/cache/` keyed by `(model, prompt hash)`. Budget caps stop cleanly before overspend; at most one retry per call.

The match judge prefers `OPENAI_*` (`gpt-4o-mini`). If those are unset, `score.py` falls back to `LLM_*` so a local dry run can still save judgement files — set `OPENAI_API_KEY` before a formal run.

## Env

Uses the app’s `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` for baseline DeepSeek (or whatever the app uses). Optional `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` for a second baseline and for the match judge. See `.env.example`. Never commit real keys.
