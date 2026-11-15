# Benchmark v2 results, run v2_full_20261115T003855Z

40 frozen cases (29 with planted bugs holding 32 bugs, 11 correct), one run per case, serial. Baselines: one plain-LLM review per case (DeepSeek `deepseek-chat`, OpenAI `gpt-4o-mini`). Hexorcist: Find-bugs mode over the live API with `deepseek-chat`. Every patch is checked against the frozen checks. Match judge: `gpt-4o-mini`, current rubric (symptom match, duplicates merged). The case files were unchanged from freeze commit `6a92c57` (verified with `git diff` and `git status`). All runs finished with no errors and no budget stop.

Strict scoring counts every unmatched report as a false alarm. Adjudicated scoring removes reports that adjudication showed to be valid findings or duplicates of a true bug (see `bench/adjudication.md`). Adjudicated recall equals strict recall.

## Overall

| Metric | Baseline DeepSeek | Baseline gpt-4o-mini | Hexorcist (DeepSeek) |
| --- | ---: | ---: | ---: |
| Detection recall (32 bugs) | 32/32 (100%) | 28/32 (88%) | 31/32 (97%) |
| False alarms per buggy case, strict | 1.72 (50) | 1.03 (30) | 0.48 (14) |
| False alarms per buggy case, adjudicated | 1.55 (45) | 0.97 (28) | 0.38 (11) |
| False alarms per correct case, strict | 2.82 (31) | 2.09 (23) | 1.18 (13) |
| False alarms per correct case, adjudicated | 2.64 (29) | 2.09 (23) | 1.09 (12) |
| Patch compiles (cases with a patch) | 40/40 (100%) | 40/40 (100%) | 37/37 (100%) |
| Verified fix on buggy cases (frozen checks) | 27/29 (93%) | 14/29 (48%) | 27/29 (93%) |
| Correct sketches given a patch | 11/11 | 11/11 | 8/11 |
| Correct sketches whose patch differs from the original | 11/11 | 9/11 | 8/11 |
| Broke a correct sketch (patch does not compile or fails frozen checks) | 0/11 | 1/11 | 0/11 |
| Median time per case | 4 s | 10 s | 100 s |
| Cost of the run | $0.027 | $0.024 | $0.241 |

Judge cost: about $0.023 (gpt-4o-mini, first scoring; re-scores used the cache). Total spend for the run: $0.315. Baselines give no verified-fix claim of their own, so their 'verified fix' is the frozen-check result of the patch they wrote. Hexorcist's own verdict was `fixed` on 14 of 29 buggy cases; the frozen checks passed on 27 of 29 (statuses: clean 3, fixed 15, partial 22).

## Hexorcist false alarms by cause

| Cause | Correct cases | Buggy cases | Total |
| --- | ---: | ---: | ---: |
| A. Sketch violates a bullet the frozen checks do not test (valid finding) | 1 | 1 | 2 |
| B. Hexorcist's assertion misreads the spec | 11 | 11 | 22 |
| C. Hexorcist's evaluator or harness is wrong | 1 | 0 | 1 |
| D. Not a false alarm (duplicate of a true bug the judge missed) | 0 | 2 | 2 |
| **Strict false alarms** | **13** | **14** | **27** |

Class C is a bug in the judge: an output pin used as a condition is read as constant 0, so `output_follows` demands the wrong level (`solenoid_ok` a2). Two more reports with the same cause (`glue_solenoid_short` a2, `mist_injector_long` a2) were credited as duplicates of the true bug, so they are not false alarms, but they kept those runs from finishing as `fixed`. A smaller evaluator weakness gives 1 to 3 ms violations at noisy threshold hovers (see adjudication). Every report on the 8 correct cases that produced one fails the same way on the known-good reference.

## Partial Hexorcist runs

22 runs ended `partial`: 15 on buggy cases and 7 on correct cases.

- Buggy cases (15): all 15 found the true bug (matched by the judge), and none missed it. 15 found it but did not verify a fix, with the caveat that the patch passed the frozen checks in 13 of 15.
- Why verification failed: in 19 of 22 partial runs every check still failing at the best patch also fails on the known-good reference, so no correct firmware could pass them. The failing checks are model-written assertions that misread the spec (class B) or hit the evaluator bug (class C).
- The other 3: `cabin_heater_mul_ovf` (5 of 25 failures not on the reference, frozen checks FAIL a_follow); `nav_beacon_byte_timer` (17 of 42 failures not on the reference, frozen checks FAIL a_max, a_period); `weather_line_prefix` (2 of 17 failures not on the reference, frozen checks pass).
- 8 of 22 partial runs had at least one patch attempt that did not compile (bench_led_miswire, boiler_ok, drip_scheduler_u8, glue_solenoid_short, solenoid_ok, walk_in_cooler_failsafe, weather_line_prefix, yard_relay_miswire).
- The one bug Hexorcist missed was the second bug of `panel_dual_debounce_edge` (inverted_pullup); that run finished `fixed`. It was not a partial run.

## By bug category

Dual-bug cases count in both of their categories. `FA` is strict false alarms per case with the adjudicated figure in brackets. Systems in order: Baseline DeepSeek / Baseline gpt-4o-mini / Hexorcist.

| Category | Cases | Bugs | Recall | Verified fix (cases) | FA per case, strict (adjudicated) |
| --- | ---: | ---: | --- | --- | --- |
| blocking delay | 3 | 3 | 3/3 / 3/3 / 3/3 | 3/3 / 2/3 / 3/3 | 2.3 (2.0) / 0.7 (0.7) / 0.0 (0.0) |
| integer overflow | 2 | 2 | 2/2 / 1/2 / 2/2 | 2/2 / 0/2 / 1/2 | 3.0 (3.0) / 1.5 (1.0) / 1.0 (0.5) |
| inverted pullup | 3 | 3 | 3/3 / 2/3 / 2/3 | 1/3 / 0/3 / 3/3 | 1.3 (1.3) / 0.7 (0.7) / 0.0 (0.0) |
| millis rollover | 2 | 2 | 2/2 / 2/2 / 2/2 | 2/2 / 1/2 / 1/2 | 2.0 (2.0) / 1.5 (1.5) / 1.0 (0.5) |
| missing debounce | 3 | 3 | 3/3 / 3/3 / 3/3 | 3/3 / 1/3 / 3/3 | 1.0 (1.0) / 0.7 (0.7) / 0.0 (0.0) |
| missing failsafe | 3 | 3 | 3/3 / 3/3 / 3/3 | 3/3 / 1/3 / 3/3 | 1.7 (1.3) / 0.7 (0.7) / 1.0 (1.0) |
| missing hysteresis | 3 | 3 | 3/3 / 3/3 / 3/3 | 3/3 / 0/3 / 3/3 | 3.0 (2.0) / 1.0 (0.7) / 0.7 (0.3) |
| off by one timing | 2 | 2 | 2/2 / 2/2 / 2/2 | 2/2 / 2/2 / 2/2 | 1.5 (1.5) / 1.0 (1.0) / 0.0 (0.0) |
| serial format | 2 | 2 | 2/2 / 1/2 / 2/2 | 2/2 / 0/2 / 2/2 | 2.5 (2.0) / 1.5 (1.5) / 2.0 (2.0) |
| stuck state machine | 2 | 2 | 2/2 / 1/2 / 2/2 | 2/2 / 1/2 / 2/2 | 1.0 (1.0) / 1.5 (1.5) / 0.0 (0.0) |
| timed pulse length | 2 | 2 | 2/2 / 2/2 / 2/2 | 2/2 / 2/2 / 2/2 | 1.5 (1.5) / 0.5 (0.5) / 0.0 (0.0) |
| wrong pin | 2 | 2 | 2/2 / 2/2 / 2/2 | 2/2 / 2/2 / 2/2 | 1.5 (1.5) / 1.5 (1.5) / 0.0 (0.0) |
| wrong unit scaling | 3 | 3 | 3/3 / 3/3 / 3/3 | 3/3 / 3/3 / 3/3 | 0.3 (0.3) / 0.7 (0.7) / 0.3 (0.3) |
| correct | 11 | - | n/a | n/a | 2.8 (2.6) / 2.1 (2.1) / 1.2 (1.1) |

## Findings

- **Recall.** DeepSeek baseline found 32 of 32 bugs, Hexorcist 31, gpt-4o-mini 28. The planted bugs are mostly visible in the code, so a plain review does well here. Hexorcist's one miss was the second bug of a dual-bug case (`panel_dual_debounce_edge`, inverted pull-up). gpt-4o-mini missed 4, including the integer overflow in `blend_tank_sum_ovf`.
- **Reports per case.** Strict false alarms per correct case: 2.8 (DeepSeek), 2.1 (gpt-4o-mini), 1.2 (Hexorcist); per buggy case 1.7, 1.0, 0.5. Baseline claims on correct sketches are mostly speculation ("minor", "fragile") or contradict the spec. Hexorcist's reports on correct sketches come with measured numbers, but each one fails the same way on the known-good firmware, so the numbers are accurate and the check is wrong.
- **Fixes.** Patches passed the frozen checks on 27 of 29 buggy cases for Hexorcist, 27 for the DeepSeek baseline and 14 for gpt-4o-mini. Hexorcist did best on inverted pull-up (3/3, against 1/3 for DeepSeek) and lost on integer overflow (1/2; the `cabin_heater_mul_ovf` patch fails `a_follow`) and millis rollover (1/2; the `nav_beacon_byte_timer` patch fails `a_max` and `a_period`).
- **Correct sketches.** Hexorcist left 3 of 11 alone (no report, no patch) and rewrote 8; none of its patches failed the frozen checks. The baselines are asked for a patched sketch every time and rewrote 11/11 (DeepSeek) and 9/11 (gpt-4o-mini); one gpt-4o-mini rewrite (`loft_fan_ok`) failed the frozen checks.
- **Behaviours the frozen checks miss.** Four defects, confirmed by measurement (pct period, toggle limit, porch restart) or by reading the code in both sketch and reference (freeze): the pct stream stretching to 1246 ms while the force button is held (`blend_tank_sum_ovf`, found by Hexorcist and by gpt-4o-mini), and fan toggling past 2 per 5 s under boost presses (`loft_fan_ok`, found by Hexorcist and the DeepSeek baseline). The DeepSeek baseline also found that the freeze in `weather_ok` and `weather_line_prefix` never freezes (the sketch re-latches the value on every loop; Hexorcist wrote no freeze assertion in either run), and that `porch_gate_block` restarts the chime for a press that began while it was sounding (3600 ms pulse; the reference ignores the press).
- **Where Hexorcist loses.** After adjudication, 22 of its 23 remaining false alarms are assertions that misread the spec and 1 is an evaluator bug. A run ends `partial` when such a check cannot be satisfied, and the loop keeps patching to meet it: 14 of 29 buggy cases reached Hexorcist's own `fixed` status while 27 passed the frozen checks. It is slower (median 100 s against 4 s for the DeepSeek baseline) and costs $0.241 per 40 cases against $0.027.
- **Evidence strength.** For 28 of 31 detected bugs, at least one matched report failed on a scenario where the known-good firmware passes. For `drip_scheduler_u8`, `hold_to_arm_late`, `vault_lock_stuck` the judge matched a report to the true bug, but the check that report cites fails the same way on the reference, so its measured evidence does not separate the buggy sketch from the correct one (for `drip_scheduler_u8` the numbers differ in size but not in outcome).
- **Gaps in the frozen set.** The reference firmware itself violates a spec bullet in 5 cases: the freeze (`weather_ok`, `weather_line_prefix`), the toggle limit under button presses (`loft_fan_ok`, `attic_vent_hyst`) and the pct period with the button held (`blend_tank_sum_ovf`). Of the 34 cases with a digital input, 17 have no frozen scenario that drives any digital input, and 4 more leave one input undriven. These are recorded here and the cases are unchanged.

## Limitations

- 40 cases and one Hexorcist run per case. The app is not deterministic, so differences of a few bugs or false alarms are within run-to-run noise.
- The cases were written for this benchmark, by the project author, with planted bugs from a fixed list of 13 categories. Results may not transfer to real firmware.
- Hexorcist's prompts were tuned on DeepSeek and on the four buggy preset firmwares, not on these cases. The baseline prompt was not tuned.
- The baseline is one plain-LLM review per case. A stronger prompt, tool use or a larger model could do better.
- Matching and false-alarm counting use an LLM judge (gpt-4o-mini). It returned 6 false-alarm indices that name no report (dropped in the scorer) and missed some duplicates. Baseline claims were adjudicated by reading, not by running each claim, so the baseline 'valid' counts are a lower bound.
- Verified fix means passing the frozen checks. They are hand-written and have the gaps above, so a patch can pass and still break an untested bullet.
- The frozen checks are scored with the same `evaluate_all` code that Hexorcist uses as its judge. An evaluator weakness can therefore hide in the ground truth too: the `porch_gate_block` restart above passes the frozen `a_pulse` check because the evaluator lets a held trigger fire again.
- Adjudication was done once, by the agent that ran the benchmark, after seeing the results.

Files: `bench/adjudication.md`, `bench/adjudication.json`, `bench/results/v2_full_20261115T003855Z_*.json`, `bench/results/v2_full_20261115T003855Z_replay.json`, `bench/results/asscored/`, `bench/results/run.log`.
