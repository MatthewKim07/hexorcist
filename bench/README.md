# Hexorcist benchmark

Compare three things on the **same** sketches, graded by the **same** ground-truth checks:

| System | What it is |
| --- | --- |
| **A – Baseline** | Plain LLM code review: sketch + spec + pins → bug list + full patched sketch. No compiler, no emulator (`run_baseline.py`). |
| **B – Hexorcist** | Find-bugs mode through the real HTTP API (`run_hexorcist.py`). |
| **C – Ground truth** | Hand-written `checks.json` scenarios/assertions + `reference.ino` per case. |

Presets used for product tuning (`thermostat`, `button`, `logger`, `alarm`, `containment`) are **not** in this dataset.

## Dataset versions

- **v1** (archived under `bench/archive/v1/`): discarded. Sketches were too short (median ~8 non-blank lines vs a 30–150 target), some comments revealed bugs, and several `spec.md` files omitted requirements that `checks.json` tested. Only a **3-case dry run** was ever executed against v1; there was no full run.
- **v2** (current `bench/cases/`): hand-written realistic sketches, specs that cover every check, linted for bug-hinting language. See freeze section below after validation.

## Freeze rule

**`bench/cases/` is frozen after the v2 freeze commit.** Do not add, edit, or delete cases to improve scores. Do not tune Hexorcist prompts, judges, or agent loops against these cases. If a case is wrong, document it and ship a later versioned dataset — never silently reshape the frozen set during a leaderboard run.

## Layout

```
bench/cases/<id>/
  sketch.ino      # under test (Allman braces)
  reference.ino   # known-good
  spec.md         # product-style bullet requirements (with numbers)
  pins.json       # app PinSpec list
  truth.json      # real bugs (or [])
  checks.json     # frozen assertions + stimulus; each assertion has "covers"
```

## Commands

From the repo root (sandbox image required for validate/score verify):

```bash
backend/.venv/bin/python -m bench.lint_cases
backend/.venv/bin/python -m bench.validate

backend/.venv/bin/python -m bench.run_baseline --max-cost-deepseek 0.80 --max-cost-openai 3.00 CASE_ID...
backend/.venv/bin/python -m bench.run_hexorcist --api http://127.0.0.1:8080 CASE_ID...
backend/.venv/bin/python -m bench.score --baseline bench/results/….json --hexorcist bench/results/….json \
  --max-cost-deepseek 0.80 --max-cost-openai 3.00
```

LLM responses are cached under `bench/cache/` keyed by `(model, prompt hash)`. Budget caps stop cleanly before overspend; at most one retry per call.

The match judge prefers `OPENAI_*` (`gpt-4o-mini`). If those are unset, `score.py` falls back to `LLM_*`.

## Env

Uses the app’s `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`. Optional `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` for a second baseline and for the match judge. See `.env.example`. Never commit real keys.
