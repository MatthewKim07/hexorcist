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
- **v2** (current `bench/cases/`): hand-written realistic sketches, specs that cover every check, linted for bug-hinting language.
  - **Frozen** at commit `6a92c57`, 40 cases, 240 files. Fingerprint from `bench/freeze_hash.py` (method documented in the script): `330d5ca3f0e29c6b30c4e54e30ef7b217cf86e3c35326d7c77131e01984a98d8`. Verify with `python bench/freeze_hash.py --check`. The same value comes out of a `git archive` of the freeze commit. The earlier hash `6512d059…` in this file used an undocumented method and could not be reproduced, so it is retired.
  - Dry run `dry_v2_20261114T230218Z` (3 cases), then the full run `v2_full_20261115T003855Z`: all 40 cases, three systems, results in `bench/results/summary.md`, false-alarm review in `bench/adjudication.md`.

## Freeze rule

**`bench/cases/` is frozen.** Do not add, edit, or delete cases to improve scores. Do not tune Hexorcist prompts, judges, or agent loops against these cases. If a case is wrong, document it and ship a later versioned dataset — never silently reshape the frozen set during a leaderboard run.

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

## Full run

`bench/run_all.sh` rebuilds the stack, checks health, and runs both baselines and Hexorcist over all 40 cases with budget caps and caching (about 2 hours). It raises the app's rate limit for the run only, through `bench/docker-compose.bench.yml`. Then score with `bench.score`, review with `bench.summarize`:

```bash
bench/run_all.sh
backend/.venv/bin/python -m bench.score --run-id RUN_score_deepseek --baseline bench/results/RUN_baseline_deepseek.json --hexorcist bench/results/RUN_hexorcist.json
backend/.venv/bin/python -m bench.score --run-id RUN_score_openai --baseline bench/results/RUN_baseline_openai.json
backend/.venv/bin/python -m bench.summarize RUN
```

`bench.summarize` reads `bench/adjudication.json` (manual verdicts with run evidence) and `bench/results/RUN_replay.json` (known-good firmware replayed through each Hexorcist run's own checks).

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

## Strong-model baseline (optional, not run yet)

A third plain-review baseline with a stronger OpenAI model, same prompt and same scoring as the other two. Set `BASELINE_STRONG_MODEL` (empty in `.env.example`, so it is off by default) and run:

```bash
backend/.venv/bin/python -m bench.run_baseline --endpoint strong --max-cost-strong 2.00 --run-id RUN_baseline_strong
backend/.venv/bin/python -m bench.score --run-id RUN_score_strong --baseline bench/results/RUN_baseline_strong.json
```

It uses the `OPENAI_*` account and has its own cost cap (`--max-cost-strong`, default $2.00), tallied apart from the gpt-4o-mini baseline and the judge. A model missing from the price table in `bench/llm_budget.py` is priced as `gpt-4o`, so the cap still bites. A reasoning model (`o3`, `gpt-5`) needs `--max-tokens 16000`, because it spends part of the completion budget thinking.

## Env

Uses the app’s `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`. Optional `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` for a second baseline and for the match judge. See `.env.example`. Never commit real keys.
