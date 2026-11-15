# DEV-set comparison: `dev_full_20261115T091310Z` against `v2_full_20261115T003855Z`

**These are DEV-set results.** Benchmark v2 has been seen: its false alarms were read and adjudicated, and the agent was changed in response. The numbers show whether the changes work. They are not final evidence, and a held-out v3 set does not exist yet. One run per case on both sides, so differences of a few cases are within run-to-run noise.

Old run: the agent as benchmarked on 2026-11-15 (adjudicated in `bench/adjudication.md`). New run: the same 40 frozen cases through the agent with the evaluator fix, clean-room cross-check, spec grounding and stimulus search (commits up to `b095256`), DeepSeek `deepseek-chat` both times. Scoring is `bench.score` with the same gpt-4o-mini judge and the same frozen checks. Cost is the DeepSeek cost of the Hexorcist runs (the judge is extra, about $0.006 for the new run).

## Verdict

The changes did what they were built to do on false alarms, and cost recall. Strict false alarms fell from 27 to 6 and the agent now leaves correct sketches alone. But it found 24 of 32 planted bugs instead of 31, and verified fixes on the frozen checks fell from 27 to 21 of 29 buggy cases. The recall loss is caused by the cross-check dropping checks that were real, and it shows as 7 planted-bug sketches that now get a `clean` verdict: a false all-clear is worse than a false alarm. The stimulus search found nothing on these 40 cases. Net: not a clear improvement yet. It is a precision gain bought with recall, and part of the recall loss is fixable (see "Where the recall went").

## Overall

| Metric | Old | New |
| --- | ---: | ---: |
| Detection recall (32 bugs) | 31/32 (97%) | 24/32 (75%) |
| False alarms per buggy case, strict | 0.48 (14) | 0.17 (5) |
| False alarms per correct case, strict | 1.18 (13) | 0.09 (1) |
| Verified fix on buggy cases (frozen checks) | 27/29 (93%) | 21/29 (72%) |
| Own status `fixed` | 15 (14 buggy) | 17 (16 buggy) |
| `fixed` claims whose patch passes the frozen checks | 15/15 | 16/17 |
| Statuses | clean 3, fixed 15, partial 22 | clean 17, fixed 17, partial 6 |
| Correct sketches given a patch (of 11) | 8 | 1 |
| Correct sketch broken by its patch (fails frozen checks) | 0 | 1 |
| Cost of the 40 runs | $0.241 | $0.165 |
| Median time per case | 100 s | 115 s |
| Total time | 70 min | 88 min |

- **Fixed claims.** 16 of the 17 `fixed` claims pass the frozen checks. The exception is `loft_fan_ok`, a correct sketch: the agent confirmed a real violation of the toggle limit under button presses (the sketch does break that bullet, see below), "fixed" it, and the patch fails the frozen `a_follow` check. Before, that run ended `partial` without claiming a fix.
- **Cost and time.** Cost fell about 31% because far fewer runs went through the fix loop. Median time rose 14% (100 s to 115 s), total time 27%, well under the 2x target. The extra time is the clean-room run and the search (below).

## New steps

| | |
| --- | --- |
| Clean-room cross-check | ran in 35 cases, not needed in 5 (no failures to classify), skipped in 0. 33,547 tokens for the clean-room sketches in all, 53 min of container time |
| Unconfirmed checks | 27 in 16 cases |
| Spec grounding | 0 of 153 assertions dropped: the model quoted the spec correctly every time, so this step did nothing here |
| Stimulus search | 1,200 variants run, 3 broke a check that had not failed, **0 bugs found by search**, 1 finding discarded by the clean room (`drip_scheduler_u8` a1). Median 39 s per case, 1.6 h of container time in all |

**Search found nothing.** On these 40 cases it neither found a new bug nor caused a false alarm. That only shows it is safe here: the model's own scenarios plus the built-in library already covered every planted bug that any confirmed check could see. Whether the search can find bugs those scenarios miss is not shown. It costs about 40 s of wall time per case.

## Unconfirmed checks, replayed on the known-good reference

All 27 unconfirmed checks were replayed on each case's `reference.ino` (`bench/replay_run.py`, results in `dev_full_20261115T091310Z_replay.json`).

- **25 fail on the reference too.** No correct firmware passes them, so dropping them was right. These are the false alarms the cross-check removed.
- **2 pass on the reference**, so they were real: `glue_solenoid_short` a1 (the pulse-length bug, 14 of 14 failing scenarios pass on the reference) and `rail_limit_invert` a1 (the inverted limit, 18 of 18). Both are checks on a planted bug, wrongly dropped.
- Two more drop a check that fails on the reference in some scenarios but not in others: `bench_led_miswire` a1 (fails on the uploaded sketch in 5 scenarios where the reference passes) and `cabin_heater_mul_ovf` a1 (2 such scenarios).

## Where the recall went

Eight buggy cases are missed in the new run, against one in the old (`panel_dual_debounce_edge`, its second bug, missed both times).

| Case | Why |
| --- | --- |
| `glue_solenoid_short`, `rail_limit_invert` | The one check on the bug passes on the reference but the clean-room sketch also failed it (12 of 14 and 17 of 18 scenarios), so it was dropped. So the clean-room sketch was itself wrong (for `glue_solenoid_short` its pulse never ended) or read the spec the same wrong way. I read the first, not the second. A flawed clean room hides a real bug. |
| `bench_led_miswire`, `cabin_heater_mul_ovf` | The check on the bug fails on the reference in a few scenarios (small violations of 2 to 20 ms at thresholds) and fails on the clean room in about half of the uploaded sketch's failing scenarios, which is enough to drop it at the 50% rule. |
| `drip_scheduler_u8`, `hold_to_arm_late`, `vault_lock_stuck` | In the old run these counted as found, but only through checks that fail identically on the reference (already noted in `bench/adjudication.md`). They did not separate the buggy sketch from the correct one. The new run drops those checks, which is correct, and nothing else catches the bug. |

So of the 7 new misses, 3 were not real detections before and 4 are real losses to the cross-check. With those 4 recovered the new recall would be about 28 of 32, still below the old 31 because the old number counted 3 non-discriminating detections. Whether to count those is a judgment call. I would not.

## Remaining false alarms (6)

Classified by reference replay: a report is class B when its check fails on the reference in at least half of the scenarios where it fails on the uploaded sketch, so no correct firmware passes it. Otherwise it is "not B": the reference passes where the sketch fails, so the check measures something real.

| Case | Report | Reference fails in same scenarios | Class |
| --- | --- | ---: | --- |
| aquarium_ph_scale (buggy) | Alert LED driven from unscaled millivolt value (a3) | 9% | not B |
| attic_vent_hyst (buggy) | Relay chatters because each 50 ms sample re-evaluates a noisy threshold with no filtering  (a3) | 29% | not B |
| blend_tank_sum_ovf (buggy) | Blocking delay in button handling and window-based printing break the 1 s cadence (a2) | 100% | B |
| loft_fan_ok (correct) | Boost button toggles fan on every press with no rate limit (a3) | 100% | B |
| process_dual_block_scale (buggy) | Alarm threshold compared against raw ADC counts (a3) | 0% | not B |
| workshop_kpa_scale (buggy) | Gauge lamp driven from offset-corrupted pressure (a3) | 62% | B |

Read from the titles and evidence, not adjudicated: the three "not B" reports (`aquarium_ph_scale`, `attic_vent_hyst`, `process_dual_block_scale`) each describe the planted bug of their case in other words, so they are duplicates the judge did not merge. The three B reports are the same ones the first adjudication found: the `blend_tank_sum_ovf` pct period with the force button held and the `loft_fan_ok` toggle limit under presses (both are real violations that the reference firmware shares, hence B), and `workshop_kpa_scale` a3.

Old run for comparison, from `bench/adjudication.md`: 27 false alarms, of which 22 class B, 2 valid findings, 1 evaluator bug, 2 judge duplicates.

## `nav_beacon_byte_timer` recheck (`dev_nav_recheck_20261115T091016Z`)

- `serial_period` is now **confirmed**: it is reported as a bug ("Tick interval is half the required period"). The only unconfirmed check is `a1` (the beacon must be HIGH whenever the switch is released, a check that misreads a blinking beacon).
- The patch still **fails `a_max` and `a_period`** (`partial`, three attempts). So the fix to the cross-check was needed but did not make the agent fix this bug. The same result came out of the full dev run. Run-to-run: both times the best patch fails the same two frozen checks, so this is the fix loop failing on an 8-bit millis rollover, not the cross-check.

## Per case

| Case | Category | Status old → new | Detected old → new | False alarms old → new | Unconfirmed | Found by search | Frozen checks on the patch old → new |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| aquarium_ph_scale | wrong_unit_scaling | fixed → partial | 1/1 → 1/1 | 0 → 1 | 0 | no | pass → pass |
| attic_vent_hyst | missing_hysteresis | partial → partial | 1/1 → 1/1 | 1 → 1 | 0 | no | pass → pass |
| bench_led_miswire | wrong_pin | partial → clean | 1/1 → 0/1 | 0 → 0 | 2 | no | pass → no patch |
| blend_tank_sum_ovf | integer_overflow | fixed → fixed | 1/1 → 1/1 | 1 → 1 | 0 | no | pass → pass |
| boiler_ok | correct | partial → clean | - → - | 2 → 0 | 1 | no | pass → no patch |
| boiler_valve_failsafe | missing_failsafe | partial → fixed | 1/1 → 1/1 | 2 → 0 | 1 | no | pass → pass |
| cabin_heater_mul_ovf | integer_overflow | partial → clean | 1/1 → 0/1 | 1 → 0 | 1 | no | FAIL → no patch |
| cellar_pump_hyst | missing_hysteresis | partial → fixed | 1/1 → 1/1 | 1 → 0 | 0 | no | pass → pass |
| cooler_ok | correct | partial → clean | - → - | 1 → 0 | 0 | no | pass → no patch |
| drip_scheduler_u8 | millis_rollover | partial → clean | 1/1 → 0/1 | 1 → 0 | 4 | no | pass → no patch |
| foyer_lamp_debounce | missing_debounce | fixed → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| glue_solenoid_short | timed_pulse_length | partial → clean | 1/1 → 0/1 | 0 → 0 | 1 | no | pass → no patch |
| greenhouse_dual | missing_hysteresis, missing_failsafe | fixed → fixed | 2/2 → 2/2 | 0 → 0 | 0 | no | pass → pass |
| greenhouse_ok | correct | clean → clean | - → - | 0 → 0 | 0 | no | no patch → no patch |
| hoist_estop_invert | inverted_pullup | fixed → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| hold_to_arm_late | off_by_one_timing | partial → clean | 1/1 → 0/1 | 0 → 0 | 1 | no | pass → no patch |
| inject_pulse_short | off_by_one_timing | fixed → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| kiln_door_block | blocking_delay | fixed → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| lab_ph_ok | correct | partial → clean | - → - | 2 → 0 | 2 | no | pass → no patch |
| laundry_cycle_stuck | stuck_state_machine | fixed → partial | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| laundry_ok | correct | fixed → clean | - → - | 1 → 0 | 1 | no | pass → no patch |
| lobby_lamp_ok | correct | clean → clean | - → - | 0 → 0 | 0 | no | no patch → no patch |
| lock_ok | correct | partial → clean | - → - | 1 → 0 | 2 | no | pass → no patch |
| loft_fan_ok | correct | partial → fixed | - → - | 3 → 1 | 2 | no | pass → FAIL |
| mist_injector_long | timed_pulse_length | partial → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| nav_beacon_byte_timer | millis_rollover | partial → partial | 1/1 → 1/1 | 1 → 0 | 0 | no | FAIL → FAIL |
| panel_dual_debounce_edge | missing_debounce, inverted_pullup | fixed → fixed | 1/2 → 1/2 | 0 → 0 | 0 | no | pass → pass |
| porch_gate_block | blocking_delay | fixed → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| process_dual_block_scale | wrong_unit_scaling, blocking_delay | fixed → partial | 2/2 → 2/2 | 0 → 1 | 0 | no | pass → pass |
| rail_limit_invert | inverted_pullup | fixed → clean | 1/1 → 0/1 | 0 → 0 | 1 | no | pass → no patch |
| shop_estop_debounce | missing_debounce | fixed → fixed | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |
| solenoid_ok | correct | partial → clean | - → - | 1 → 0 | 0 | no | pass → no patch |
| spindle_rpm_prefix | serial_format | partial → fixed | 1/1 → 1/1 | 2 → 0 | 2 | no | pass → pass |
| studio_siren_ok | correct | clean → clean | - → - | 0 → 0 | 0 | no | no patch → no patch |
| vault_lock_stuck | stuck_state_machine | partial → clean | 1/1 → 0/1 | 0 → 0 | 2 | no | pass → no patch |
| walk_in_cooler_failsafe | missing_failsafe | partial → fixed | 1/1 → 1/1 | 1 → 0 | 0 | no | pass → pass |
| weather_line_prefix | serial_format | partial → fixed | 1/1 → 1/1 | 2 → 0 | 2 | no | pass → pass |
| weather_ok | correct | partial → clean | - → - | 2 → 0 | 2 | no | pass → no patch |
| workshop_kpa_scale | wrong_unit_scaling | fixed → fixed | 1/1 → 1/1 | 1 → 1 | 0 | no | pass → pass |
| yard_relay_miswire | wrong_pin | partial → partial | 1/1 → 1/1 | 0 → 0 | 0 | no | pass → pass |

## What to do next

1. The cross-check is too eager at the 50% rule with a single clean-room sketch. Options, cheapest first: require the clean room to fail the check in nearly all of the uploaded sketch's failing scenarios (would likely recover `bench_led_miswire` and `cabin_heater_mul_ovf`, and would bring back some false alarms such as `solenoid_ok` a2 at 14 of 16); draw a second clean-room sketch and drop a check only when both fail it (guards against one flawed clean room and might recover `glue_solenoid_short` and `rail_limit_invert`; an estimate of about $0.003 and 25 s per run, not measured). Tuning either on v2 makes v2 even less of a test, so it needs v3 to be judged.
2. Evaluator: 1 to 3 ms violations at noisy thresholds still make checks fail on the reference (class C2 in the first adjudication). A minimum violation length would remove that, but it changes frozen verdicts and needs its own validation run.
3. The search needs a case where the planned scenarios miss a bug before anything can be said about it. v3 should include some.

Files: `bench/results/dev_full_20261115T091310Z_{hexorcist,score,replay}.json`, `bench/results/dev_nav_recheck_20261115T091016Z_*`, `bench/dev_compare.py`, `bench/replay_run.py`. The smoke run `dev_smoke_20261115T084912Z` (5 cases, before the `b095256` fix) is not part of these numbers.
