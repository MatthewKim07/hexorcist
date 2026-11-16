# DEV-set comparison, four runs

**DEV-set results.** Benchmark v2 has been seen and is now tuned on, on purpose. These numbers show whether the changes work. They are not evidence about unseen firmware: that needs the held-out v3 set, which does not exist yet. One run per case per column, so a difference of a few cases is within run-to-run noise. Every run also regenerates the checks from the spec, so a case can change result with no change in the agent.

| Column | Run | Agent |
| --- | --- | --- |
| old | `v2_full_20261115T003855Z` | the first benchmark: no cross-check, no search |
| one room | `dev_full_20261115T091310Z` | evaluator fix, one clean-room sketch (dropped if it fails the check in 50% of scenarios), spec grounding, search |
| two rooms | `dev_full2_20261115T222332Z` | two independent clean-room sketches from DeepSeek, a check is dropped only if both fail it the same way in at least 80% of the scenarios where the uploaded sketch fails it; same search |
| mixed rooms | `dev_full3_20261116T081621Z` | same rule, but room 1 is `deepseek-chat` and room 2 is `gpt-4o-mini`; search off (its acceptance gates were not exercised) |

Same 40 frozen cases, same gpt-4o-mini judge, same frozen checks. The agent model is `deepseek-chat` in every run. Cost is the Hexorcist cost of each run (judge extra, about $0.006).

## Verdict

**Model diversity recovered `rail_limit_invert` but not `glue_solenoid_short`, and false alarms went up, not down: 14 strict, against 12 in the two-room run (10 without the two the search produced) and 6 in the one-room run.**

- `rail_limit_invert` is detected and fixed (frozen checks pass). Its check was kept, so the two-room rule no longer dropped it.
- `glue_solenoid_short` is still missed. Both rooms, including the `gpt-4o-mini` one, failed `a1` (`timed_pulse`) in 13 of the 14 scenarios where the uploaded sketch fails, with near-identical evidence ("pulse from 1.03 s was still on after 6968 ms" and "after 6967 ms"). The reference passes that check, so a real check was dropped, as in the two-room run. A second model did not give a second opinion here.
- `bench_led_miswire` was lost (found in the two-room run, missed now). Its reported check `a1` fails on the reference in 7 scenarios, which is 64% of the scenarios where it fails on the sketch, so it is a class B false alarm and the judge did not match it to the planted bug. One run cannot separate this from noise.
- Recall is 27/32, the same as the two-room run. Honest recall is **26/32**, up from 25 and equal to the first run. The only hollow detection left is `nav_beacon_byte_timer`.
- Strict false alarms: 9 on buggy cases and 5 on correct ones. Of the 14, 11 sit on checks that also fail on the known-good reference (class B). Nine are new against the two-room run and seven are gone. I did not test why: that a weaker second model writes rooms that fail the checks less often than DeepSeek's rooms is a hypothesis.
- Verified fix on the frozen checks is 23/29 (79%), against 24/29 in the two-room run. Every one of the 17 `fixed` claims passes the frozen checks.
- Cost is $0.215 for 40 runs (DeepSeek $0.201, OpenAI $0.014). Median time per case is 114 s, 1.14x the first run, with the search off.

## Run audit: did room 2 really run on gpt-4o-mini?

From the 40 case rows (`cross_check`, `providers`) and `run_dev.log`:

| Check | Result |
| --- | --- |
| Rows with `model_diversity.mixed` true and `fallback` false | 40 of 40 |
| Cases where the cross-check ran | 34 |
| Room 2 `ready` on `gpt-4o-mini` at `api.openai.com` | 34 of 34 (4 needed the repair retry after a compile failure) |
| Room 1 `ready` on `deepseek-chat` | 34 of 34 |
| Rooms skipped or failed | 0 |
| Fallbacks to DeepSeek for room 2 | 0 |
| 401, 403, 429 or key errors in the log | none |
| Cases where the cross-check was not needed | 6 (`boiler_ok`, `cooler_ok`, `greenhouse_ok`, `lobby_lamp_ok`, `solenoid_ok`, `studio_siren_ok`): the uploaded sketch had no failing check, so no rooms were recorded. `gpt-4o-mini` was still called in them (1 to 2 calls each) and billed |
| Agent calls to a host other than `api.deepseek.com` | none |
| Search | off in all 40 rows (0 variants) |

So room 2 ran on `gpt-4o-mini` in every case that needed a cross-check, which is 34 of 40, not all 40.

Spend, from the per-row buckets and the log: **DeepSeek $0.2008** (cap $0.60) and **OpenAI $0.0141** (cap $0.50) for the 40 runs, plus $0.0061 OpenAI for scoring (28 judge calls). Nothing in other buckets.

## Overall

| Metric | old | one room | two rooms | mixed rooms |
| --- | ---: | ---: | ---: | ---: |
| Detection recall (32 bugs) | 31/32 (97%) | 24/32 (75%) | 27/32 (84%) | 27/32 (84%) |
| **Honest recall** (see below) | 26/32 (81%) | 22/32 (69%) | 25/32 (78%) | 26/32 (81%) |
| False alarms per buggy case, strict | 0.48 (14) | 0.17 (5) | 0.24 (7) | 0.31 (9) |
| False alarms per correct case, strict | 1.18 (13) | 0.09 (1) | 0.45 (5) | 0.45 (5) |
| Verified fix on buggy cases (frozen checks) | 27/29 (93%) | 21/29 (72%) | 24/29 (83%) | 23/29 (79%) |
| Own status `fixed` | 15 | 17 | 18 | 17 |
| Fixed-claim precision (claims whose patch passes the frozen checks) | 15/15 | 16/17 | 18/18 | 17/17 |
| Statuses clean / fixed / partial | 3 / 15 / 22 | 17 / 17 / 6 | 12 / 18 / 10 | 11 / 17 / 12 |
| Correct sketches given a patch (of 11) | 8 | 1 | 3 | 3 |
| Correct sketch broken by its patch | 0 | 1 | 0 | 0 |
| Unconfirmed checks (cases) | n/a | 27 (16) | 20 (16) | 17 (12) |
| ...of which fail on the reference too (rightly dropped) | n/a | 25 | 18 | 16 |
| ...of which pass on the reference (real checks wrongly dropped) | n/a | 2 | 2 | 1 |
| Bugs found by search | n/a | 0 | 4 | 0 (search off) |
| Cost of the 40 runs | $0.241 | $0.165 | $0.208 | $0.215 (DeepSeek $0.201, OpenAI $0.014) |
| Median time per case | 100 s | 115 s | 164 s | 114 s |
| Total time | 70 min | 88 min | 118 min | 85 min |

**Honest recall.** A planted bug counts only if a report the judge matched to it has a check that fails on the uploaded sketch in some scenario where the known-good `reference.ino` passes. A matched report whose check fails identically on the reference is a coincidence of wording, not a detection: it would flag the correct sketch just as well. By this measure the old 31 were really 26 (`attic_vent_hyst`, `drip_scheduler_u8`, `hold_to_arm_late`, `nav_beacon_byte_timer` and `vault_lock_stuck` were matched only through such reports). It is a stricter test than the first adjudication used, which counted any matched or duplicate report that separated the two, so the old figure here is 26, not 28.

The one unconfirmed check that passes on the reference in the mixed run is `glue_solenoid_short` a1. The cross-check cost 75,712 tokens and 1.7 h of container time (two rooms: 70,644 and 1.8 h).

## Mixed rooms, case by case

Missed in the mixed run: `bench_led_miswire`, `glue_solenoid_short`, `hold_to_arm_late`, `panel_dual_debounce_edge`, `vault_lock_stuck`. Compared with the two-room run, `rail_limit_invert` came back and `bench_led_miswire` was lost.

| Case | Two rooms | Mixed rooms | Note |
| --- | --- | --- | --- |
| `rail_limit_invert` | missed | detected, fixed | the `a1` check is no longer unconfirmed; per-room evidence for kept checks is not stored, so I cannot say which room disagreed |
| `glue_solenoid_short` | missed | missed | both rooms fail `a1` in 13 of 14 shared scenarios, evidence identical to within 1 ms; the reference passes |
| `bench_led_miswire` | detected | missed | reported `a1` is class B (reference fails in 7 scenarios); `a2` was dropped rightly (the reference fails it in 18 scenarios) |

## False alarms in the mixed run (14 strict)

Class B: the check also fails on the known-good reference in at least half of the scenarios where it fails on the uploaded sketch. Not B: the reference passes where the sketch fails.

| Case | Report | Reference fails in same scenarios | Class |
| --- | --- | ---: | --- |
| aquarium_ph_scale (buggy) | Alert LED driven from unscaled millivolt value (a3) | 10% | not B |
| bench_led_miswire (buggy) | Blink mode re-initialization and stale lit state (a1) | 64% | B |
| blend_tank_sum_ovf (buggy) | Button handling with delay(30) stalls the periodic pct stream (a2) | 100% | B |
| cabin_heater_mul_ovf (buggy) | Frost override not honored reliably while D2 is LOW (a2) | 100% | B |
| lab_ph_ok (correct) | Range lamp chatters at the 6.50 pH threshold (a3) | 100% | B |
| lab_ph_ok (correct) | Range lamp misreports the upper band edge and glitch spikes (a4) | 100% | B |
| laundry_cycle_stuck (buggy) | Fill valve drops out on noisy or spurious level readings (a1) | 0% | not B |
| loft_fan_ok (correct) | Boost button toggles fan on every sample without debounce or rate limit (a3) | 100% | B |
| process_dual_block_scale (buggy) | Logging period is 2000 ms instead of 500 ms (a1) | 0% | not B |
| weather_line_prefix (buggy) | Range lamp chatters at the 50 °C boundary with no hysteresis (a4) | 100% | B |
| weather_line_prefix (buggy) | Range lamp chatters at the -10 °C boundary with no hysteresis (a5) | 100% | B |
| weather_ok (correct) | Range lamp chatters at the low threshold with no hysteresis (a3) | 100% | B |
| weather_ok (correct) | Range lamp driven by unvalidated/raw reading at the high threshold (a4) | 100% | B |
| workshop_kpa_scale (buggy) | Gauge lamp driven from offset-inflated pressure (a3) | 60% | B |

11 class B and 3 not B. From their titles, `aquarium_ph_scale` a3 and `process_dual_block_scale` a1 restate the case's planted bug in other words; I did not adjudicate `laundry_cycle_stuck` a1. Against the two-room run, new: `bench_led_miswire` a1, `cabin_heater_mul_ovf` a2, `lab_ph_ok` a3 and a4, `laundry_cycle_stuck` a1, `process_dual_block_scale` a1, `weather_line_prefix` a5, `weather_ok` a3, `workshop_kpa_scale` a3. Gone: the two search false alarms (`drip_scheduler_u8` a3, `greenhouse_ok` a2), `greenhouse_dual` a2, `loft_fan_ok` a1 and a2, `process_dual_block_scale` a3 and a4. Checks are regenerated every run, so "new" and "gone" partly show the same weakness (range-lamp chatter at a threshold, which the reference also fails) surfacing under different assertion ids.

Eleven of the 14 are on checks that fail on the reference, so a stricter cross-check or an evaluator fix for threshold chatter (`weather_*`, `lab_ph_ok`) would remove most of them.

## Two-room run: what the 80% rule did
Recovered as honest detections: `bench_led_miswire` and `cabin_heater_mul_ovf` (their checks fail on the uploaded sketch in scenarios where at least one clean room passes). `attic_vent_hyst` also became an honest detection. `drip_scheduler_u8` is detected again, but only through checks that fail on the reference too, so it is not an honest one.

Still missed (glue_solenoid_short, hold_to_arm_late, panel_dual_debounce_edge, rail_limit_invert, vault_lock_stuck):

| Case | Why |
| --- | --- |
| `glue_solenoid_short`, `rail_limit_invert` | Both clean rooms fail the check the same way as each other, with identical evidence strings, in 12 of 15 and 15 of 18 of the scenarios where the uploaded sketch fails. For `rail_limit_invert` the spec says "HIGH otherwise" and also "jog may request motion only when the limit is clear"; both sketches made the motor depend on the jog button, the reference follows the first bullet. That is a spec ambiguity the model reads one way every time, so a second sample from the same model does not help. The check passes on the reference, so it was a real one and the drop was wrong. |
| `hold_to_arm_late`, `vault_lock_stuck` | The first run found them only through checks that fail identically on the reference (hollow detections). They are rightly dropped, and no other check sees the bug. |
| `panel_dual_debounce_edge` | The second bug of a dual-bug case, missed in all three runs. |

## False alarms in the two-room run (12 strict)

Reference replay classes: **B** if the check also fails on the known-good reference in at least half of the scenarios where it fails on the uploaded sketch (no correct firmware passes it); **not B** otherwise (the reference passes where the sketch fails).

| Case | Report | Reference fails in same scenarios | Class | From search |
| --- | --- | ---: | --- | --- |
| aquarium_ph_scale (buggy) | Alert LED driven from unscaled millivolts, never triggers correctly (a3) | 9% | not B |  |
| blend_tank_sum_ovf (buggy) | Blocking button handling and delay stretch the pct: period (a2) | 100% | B |  |
| drip_scheduler_u8 (buggy) | Status log line never emitted in some runs (a3) | 100% | B | yes |
| greenhouse_dual (buggy) | Fan chatters because every 50 ms tick re-evaluates a single threshold with no hysteresis o (a2) | 0% | not B |  |
| greenhouse_ok (correct) | Fan toggles too often during rapid band crossings (a2) | 100% | B | yes |
| loft_fan_ok (correct) | Fan ignores hysteresis thresholds and follows boost/offHold instead (a1) | 100% | B |  |
| loft_fan_ok (correct) | Boost force-ON is not sustained; fan drops OFF while button held (a2) | 100% | B |  |
| loft_fan_ok (correct) | No rate limiting on fan toggles; boost and hysteresis cause toggle bursts (a3) | 100% | B |  |
| process_dual_block_scale (buggy) | Alarm threshold evaluated against raw ADC counts (a3) | 0% | not B |  |
| process_dual_block_scale (buggy) | Firmware silent for 2000 ms due to blocking delay (a4) | 0% | not B |  |
| weather_line_prefix (buggy) | Range lamp driven by raw instantaneous value with no hysteresis (a4) | 100% | B |  |
| weather_ok (correct) | Range lamp driven from noisy instantaneous sample instead of reported value (a4) | 100% | B |  |

8 class B and 4 not B. The not-B reports (`aquarium_ph_scale`, `process_dual_block_scale` twice, and `greenhouse_dual`) restate each case's planted bug in other words, from their titles; I did not adjudicate them further. Eight of the 12 are on checks that fail on the reference, so a better cross-check could still remove them.

Where the 6 extra false alarms against the one-room run came from: `loft_fan_ok` a1 and a2 (the 80% rule keeps checks that the clean rooms fail in only half of the scenarios), `weather_ok` a4 and `weather_line_prefix` a4 (same), and two from the search (below).

## Stimulus search: first findings in the two-room run, and not good ones

The search reported 4 bugs, in 3 cases, from 1,200 variants (5 broke a check that had not failed). Median 37 s per case. Replayed on the reference:

| Case | Search finding | Check on the reference |
| --- | --- | --- |
| `drip_scheduler_u8` a1 | missed pulse with 30 ms presses (shrunk to 2 input changes) | **fails on the reference** in 15 scenarios, the uploaded sketch in 1: a bad check. The judge matched this report to the planted bug, so it counts as a detection in the strict score and is a hollow one in the honest score |
| `drip_scheduler_u8` a3 | "status log line never emitted" | **fails on the reference**: a false alarm |
| `greenhouse_ok` a2 | "fan toggles too often during rapid band crossings", on a correct sketch | **fails on the reference**: a false alarm. The variant shifts the band crossings by 120 ms; no firmware that must follow the input can meet the toggle limit. The clean rooms passed it, so they did not catch it |
| `greenhouse_dual` a1 | no hysteresis at 24 °C, found on a variant that shifts A2 by 60 mV | passes on the reference: a real finding, but a second symptom of a planted bug that the chatter check (a2) already reports |

So one finding in four is real, and it added no bug that was not already found. Three were checks that fail on the reference, two of them false alarms and one a hollow detection, that the cross-check let through because the clean rooms happened to pass those variants. The search judges its findings with at most 12 variants and the same 80% rule. It is not safe to leave on yet.

## Cross-check cost (two-room run)

Two rooms: 70,644 tokens for the clean-room sketches in all (one room: 33,547), 1.8 h of container time (one room 0.9 h). Neither room failed to compile in any case that needed it: the cross-check ran in 36 cases and was not needed in 4.

## `nav_beacon_byte_timer`

The recheck (`dev_nav_recheck_20261115T091016Z`) confirmed `serial_period` and the patch still fails `a_max` and `a_period`, as in both full runs. This case is a fix-loop failure on an 8-bit millis rollover, not a cross-check issue. It is a good first test for the clock fast-forward.

## Per case (old / one room / two rooms / mixed rooms)

Unconfirmed is "two rooms / mixed rooms". Found by search is from the two-room run (the mixed run had the search off).

| Case | Category | Status | Detected | False alarms | Unconfirmed | Found by search | Frozen checks on the patch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aquarium_ph_scale | wrong_unit_scaling | fixed / partial / fixed / partial | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 1 / 1 / 1 | 0 / 1 | - | pass / pass / pass / pass |
| attic_vent_hyst | missing_hysteresis | partial / partial / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 | 1 / 1 / 0 / 0 | 0 / 1 | - | pass / pass / pass / pass |
| bench_led_miswire | wrong_pin | partial / clean / partial / partial | 1/1 / 0/1 / 1/1 / 0/1 | 0 / 0 / 0 / 1 | 1 / 1 | - | pass / no patch / pass / pass |
| blend_tank_sum_ovf | integer_overflow | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 1 / 1 / 1 / 1 | 0 / 0 | - | pass / pass / pass / pass |
| boiler_ok | correct | partial / clean / clean / clean | - / - / - / - | 2 / 0 / 0 / 0 | 1 / 0 | - | pass / no patch / no patch / no patch |
| boiler_valve_failsafe | missing_failsafe | partial / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 2 / 0 / 0 / 0 | 1 / 2 | - | pass / pass / pass / pass |
| cabin_heater_mul_ovf | integer_overflow | partial / clean / partial / partial | 1/1 / 0/1 / 1/1 / 1/1 | 1 / 0 / 0 / 1 | 0 / 0 | - | FAIL / no patch / pass / FAIL |
| cellar_pump_hyst | missing_hysteresis | partial / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 0 | 1 / 1 | - | pass / pass / pass / pass |
| cooler_ok | correct | partial / clean / clean / clean | - / - / - / - | 1 / 0 / 0 / 0 | 0 / 0 | - | pass / no patch / no patch / no patch |
| drip_scheduler_u8 | millis_rollover | partial / clean / partial / partial | 1/1 / 0/1 / 1/1 / 1/1 | 1 / 0 / 1 / 0 | 1 / 2 | a1, a3 | pass / no patch / pass / FAIL |
| foyer_lamp_debounce | missing_debounce | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| glue_solenoid_short | timed_pulse_length | partial / clean / clean / clean | 1/1 / 0/1 / 0/1 / 0/1 | 0 / 0 / 0 / 0 | 1 / 1 | - | pass / no patch / no patch / no patch |
| greenhouse_dual | missing_hysteresis, missing_failsafe | fixed / fixed / fixed / fixed | 2/2 / 2/2 / 2/2 / 2/2 | 0 / 0 / 1 / 0 | 0 / 0 | a1 | pass / pass / pass / pass |
| greenhouse_ok | correct | clean / clean / fixed / clean | - / - / - / - | 0 / 0 / 1 / 0 | 0 / 0 | a2 | no patch / no patch / pass / no patch |
| hoist_estop_invert | inverted_pullup | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 1 / 0 | - | pass / pass / pass / pass |
| hold_to_arm_late | off_by_one_timing | partial / clean / clean / clean | 1/1 / 0/1 / 0/1 / 0/1 | 0 / 0 / 0 / 0 | 1 / 1 | - | pass / no patch / no patch / no patch |
| inject_pulse_short | off_by_one_timing | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| kiln_door_block | blocking_delay | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| lab_ph_ok | correct | partial / clean / clean / partial | - / - / - / - | 2 / 0 / 0 / 2 | 2 / 0 | - | pass / no patch / no patch / pass |
| laundry_cycle_stuck | stuck_state_machine | fixed / partial / fixed / partial | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 1 | 0 / 0 | - | pass / pass / pass / pass |
| laundry_ok | correct | fixed / clean / clean / clean | - / - / - / - | 1 / 0 / 0 / 0 | 1 / 1 | - | pass / no patch / no patch / no patch |
| lobby_lamp_ok | correct | clean / clean / clean / clean | - / - / - / - | 0 / 0 / 0 / 0 | 0 / 0 | - | no patch / no patch / no patch / no patch |
| lock_ok | correct | partial / clean / clean / clean | - / - / - / - | 1 / 0 / 0 / 0 | 2 / 2 | - | pass / no patch / no patch / no patch |
| loft_fan_ok | correct | partial / fixed / partial / partial | - / - / - / - | 3 / 1 / 3 / 1 | 0 / 0 | - | pass / FAIL / pass / pass |
| mist_injector_long | timed_pulse_length | partial / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| nav_beacon_byte_timer | millis_rollover | partial / partial / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 0 | 0 / 0 | - | FAIL / FAIL / FAIL / FAIL |
| panel_dual_debounce_edge | missing_debounce, inverted_pullup | fixed / fixed / fixed / fixed | 1/2 / 1/2 / 1/2 / 1/2 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| porch_gate_block | blocking_delay | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| process_dual_block_scale | wrong_unit_scaling, blocking_delay | fixed / partial / partial / fixed | 2/2 / 2/2 / 2/2 / 2/2 | 0 / 1 / 2 / 1 | 0 / 0 | - | pass / pass / pass / pass |
| rail_limit_invert | inverted_pullup | fixed / clean / clean / fixed | 1/1 / 0/1 / 0/1 / 1/1 | 0 / 0 / 0 / 0 | 1 / 0 | - | pass / no patch / no patch / pass |
| shop_estop_debounce | missing_debounce | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| solenoid_ok | correct | partial / clean / clean / clean | - / - / - / - | 1 / 0 / 0 / 0 | 0 / 0 | - | pass / no patch / no patch / no patch |
| spindle_rpm_prefix | serial_format | partial / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 2 / 0 / 0 / 0 | 2 / 2 | - | pass / pass / pass / pass |
| studio_siren_ok | correct | clean / clean / clean / clean | - / - / - / - | 0 / 0 / 0 / 0 | 0 / 0 | - | no patch / no patch / no patch / no patch |
| vault_lock_stuck | stuck_state_machine | partial / clean / clean / clean | 1/1 / 0/1 / 0/1 / 0/1 | 0 / 0 / 0 / 0 | 2 / 2 | - | pass / no patch / no patch / no patch |
| walk_in_cooler_failsafe | missing_failsafe | partial / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |
| weather_line_prefix | serial_format | partial / fixed / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 | 2 / 0 / 1 / 2 | 1 / 0 | - | pass / pass / pass / pass |
| weather_ok | correct | partial / clean / partial / partial | - / - / - / - | 2 / 0 / 1 / 2 | 1 / 0 | - | pass / no patch / pass / pass |
| workshop_kpa_scale | wrong_unit_scaling | fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 | 1 / 1 / 0 / 1 | 0 / 0 | - | pass / pass / pass / pass |
| yard_relay_miswire | wrong_pin | partial / partial / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 | 0 / 0 | - | pass / pass / pass / pass |

## What to do next

1. **Cross-check:** the rule drops a check only when both rooms fail it, yet the reference replay says 11 of the 14 remaining false alarms are checks no correct firmware passes. Test a rule that also requires the room sketches to pass the check somewhere the uploaded sketch fails, or screen checks against the rooms before trusting them.
2. **Correlated rooms:** mixing models did not decorrelate `glue_solenoid_short`. The next lever is the prompt (list the spec's ambiguous bullets first and ask the second room for a different reading), not the model.
3. **Search:** still off, with acceptance gates in place and untested on real runs. Turn it on in a separate run only after the cross-check change, so the two effects stay apart.
4. **Noise:** one run per column cannot separate a two-case change from run-to-run variation. Repeat the mixed run once before reading `bench_led_miswire` or `rail_limit_invert` as a trend.

Files: `bench/results/dev_full3_20261116T081621Z_{hexorcist,score,replay}.json`, `dev_full2_20261115T222332Z_*`, `dev_full_20261115T091310Z_*`, `v2_full_20261115T003855Z_*`, `bench/dev_compare.py`, `bench/replay_run.py`.
