# DEV-set comparison, three runs

**DEV-set results.** Benchmark v2 has been seen and is now tuned on, on purpose. These numbers show whether the changes work. They are not evidence about unseen firmware: that needs the held-out v3 set, which does not exist yet. One run per case per column, so a difference of a few cases is within run-to-run noise.

| Column | Run | Agent |
| --- | --- | --- |
| old | `v2_full_20261115T003855Z` | the first benchmark: no cross-check, no search |
| one room | `dev_full_20261115T091310Z` | evaluator fix, one clean-room sketch (dropped if it fails the check in 50% of scenarios), spec grounding, search |
| two rooms | `dev_full2_20261115T222332Z` | two independent clean-room sketches, a check is dropped only if both fail it the same way in at least 80% of the scenarios where the uploaded sketch fails it; same search |

Same 40 frozen cases, same DeepSeek `deepseek-chat`, same gpt-4o-mini judge, same frozen checks. Cost is the DeepSeek cost of the Hexorcist runs (judge extra, about $0.006).

## Verdict

**The two-room rule recovered most of the lost recall without bringing back most of the false alarms, but it did not recover the two cases that motivated it, and the search added false alarms of its own.**

- Recall went from 24/32 (one room) to **27/32**; the first run had 31/32. Counting only detections whose evidence separates the buggy sketch from the correct one ("honest recall", defined below), the three runs are 26, 22 and **25** of 32: the two-room run is within one bug of the first run.
- Strict false alarms went from 6 to **12**, against 27 in the first run. Eight false alarms are new and two from the one-room run are gone. Two of the new ones come from the stimulus search, six from checks that the 80% rule no longer drops.
- `glue_solenoid_short` and `rail_limit_invert` are **still missed**. The cause is not the rule: both clean-room sketches made the same mistake, with identical evidence in both rooms, so two samples from the same model were not two independent opinions. The correlated error is the limit of this approach.
- Verified fix on the frozen checks is 24/29 (83%) (first run 27/29 (93%), one room 21/29 (72%)), and every one of the 18 `fixed` claims passes the frozen checks.
- Cost is $0.208 for 40 runs (first run $0.241). Median time per case rose to 164 s from 100 s, which is 1.63x: under the 2x target but the margin is now thin.

## Overall

| Metric | old | one room | two rooms |
| --- | ---: | ---: | ---: |
| Detection recall (32 bugs) | 31/32 (97%) | 24/32 (75%) | 27/32 (84%) |
| **Honest recall** (see below) | 26/32 (81%) | 22/32 (69%) | 25/32 (78%) |
| False alarms per buggy case, strict | 0.48 (14) | 0.17 (5) | 0.24 (7) |
| False alarms per correct case, strict | 1.18 (13) | 0.09 (1) | 0.45 (5) |
| Verified fix on buggy cases (frozen checks) | 27/29 (93%) | 21/29 (72%) | 24/29 (83%) |
| Own status `fixed` | 15 | 17 | 18 |
| Fixed-claim precision (claims whose patch passes the frozen checks) | 15/15 | 16/17 | 18/18 |
| Statuses clean / fixed / partial | 3 / 15 / 22 | 17 / 17 / 6 | 12 / 18 / 10 |
| Correct sketches given a patch (of 11) | 8 | 1 | 3 |
| Correct sketch broken by its patch | 0 | 1 | 0 |
| Unconfirmed checks (cases) | n/a | 27 (16) | 20 (16) |
| ...of which fail on the reference too (rightly dropped) | n/a | 25 | 18 |
| ...of which pass on the reference (real checks wrongly dropped) | n/a | 2 | 2 |
| Bugs found by search | n/a | 0 | 4 |
| Cost of the 40 runs | $0.241 | $0.165 | $0.208 |
| Median time per case | 100 s | 115 s | 164 s |
| Total time | 70 min | 88 min | 118 min |

**Honest recall.** A planted bug counts only if a report the judge matched to it has a check that fails on the uploaded sketch in some scenario where the known-good `reference.ino` passes. A matched report whose check fails identically on the reference is a coincidence of wording, not a detection: it would flag the correct sketch just as well. By this measure the old 31 were really 26 (`attic_vent_hyst`, `drip_scheduler_u8`, `hold_to_arm_late`, `nav_beacon_byte_timer` and `vault_lock_stuck` were matched only through such reports). It is a stricter test than the first adjudication used, which counted any matched or duplicate report that separated the two, so the old figure here is 26, not 28.

## What the two-room rule did

Recovered as honest detections: `bench_led_miswire` and `cabin_heater_mul_ovf` (their checks fail on the uploaded sketch in scenarios where at least one clean room passes). `attic_vent_hyst` also became an honest detection. `drip_scheduler_u8` is detected again, but only through checks that fail on the reference too, so it is not an honest one.

Still missed (glue_solenoid_short, hold_to_arm_late, panel_dual_debounce_edge, rail_limit_invert, vault_lock_stuck):

| Case | Why |
| --- | --- |
| `glue_solenoid_short`, `rail_limit_invert` | Both clean rooms fail the check the same way as each other, with identical evidence strings, in 12 of 15 and 15 of 18 of the scenarios where the uploaded sketch fails. For `rail_limit_invert` the spec says "HIGH otherwise" and also "jog may request motion only when the limit is clear"; both sketches made the motor depend on the jog button, the reference follows the first bullet. That is a spec ambiguity the model reads one way every time, so a second sample from the same model does not help. The check passes on the reference, so it was a real one and the drop was wrong. |
| `hold_to_arm_late`, `vault_lock_stuck` | The first run found them only through checks that fail identically on the reference (hollow detections). They are rightly dropped, and no other check sees the bug. |
| `panel_dual_debounce_edge` | The second bug of a dual-bug case, missed in all three runs. |

## False alarms (12 strict)

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

## Stimulus search: first findings, and not good ones

The search reported 4 bugs, in 3 cases, from 1,200 variants (5 broke a check that had not failed). Median 37 s per case. Replayed on the reference:

| Case | Search finding | Check on the reference |
| --- | --- | --- |
| `drip_scheduler_u8` a1 | missed pulse with 30 ms presses (shrunk to 2 input changes) | **fails on the reference** in 15 scenarios, the uploaded sketch in 1: a bad check. The judge matched this report to the planted bug, so it counts as a detection in the strict score and is a hollow one in the honest score |
| `drip_scheduler_u8` a3 | "status log line never emitted" | **fails on the reference**: a false alarm |
| `greenhouse_ok` a2 | "fan toggles too often during rapid band crossings", on a correct sketch | **fails on the reference**: a false alarm. The variant shifts the band crossings by 120 ms; no firmware that must follow the input can meet the toggle limit. The clean rooms passed it, so they did not catch it |
| `greenhouse_dual` a1 | no hysteresis at 24 °C, found on a variant that shifts A2 by 60 mV | passes on the reference: a real finding, but a second symptom of a planted bug that the chatter check (a2) already reports |

So one finding in four is real, and it added no bug that was not already found. Three were checks that fail on the reference, two of them false alarms and one a hollow detection, that the cross-check let through because the clean rooms happened to pass those variants. The search judges its findings with at most 12 variants and the same 80% rule. It is not safe to leave on yet.

## Cross-check cost

Two rooms: 70,644 tokens for the clean-room sketches in all (one room: 33,547), 1.8 h of container time (one room 0.9 h). Neither room failed to compile in any case that needed it: the cross-check ran in 36 cases and was not needed in 4.

## `nav_beacon_byte_timer`

The recheck (`dev_nav_recheck_20261115T091016Z`) confirmed `serial_period` and the patch still fails `a_max` and `a_period`, as in both full runs. This case is a fix-loop failure on an 8-bit millis rollover, not a cross-check issue. It is a good first test for the clock fast-forward.

## Per case (old / one room / two rooms)

| Case | Category | Status | Detected | False alarms | Unconfirmed (two rooms) | Found by search (two rooms) | Frozen checks on the patch |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| aquarium_ph_scale | wrong_unit_scaling | fixed / partial / fixed | 1/1 / 1/1 / 1/1 | 0 / 1 / 1 | 0 | - | pass / pass / pass |
| attic_vent_hyst | missing_hysteresis | partial / partial / partial | 1/1 / 1/1 / 1/1 | 1 / 1 / 0 | 0 | - | pass / pass / pass |
| bench_led_miswire | wrong_pin | partial / clean / partial | 1/1 / 0/1 / 1/1 | 0 / 0 / 0 | 1 | - | pass / no patch / pass |
| blend_tank_sum_ovf | integer_overflow | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 1 / 1 / 1 | 0 | - | pass / pass / pass |
| boiler_ok | correct | partial / clean / clean | - / - / - | 2 / 0 / 0 | 1 | - | pass / no patch / no patch |
| boiler_valve_failsafe | missing_failsafe | partial / fixed / fixed | 1/1 / 1/1 / 1/1 | 2 / 0 / 0 | 1 | - | pass / pass / pass |
| cabin_heater_mul_ovf | integer_overflow | partial / clean / partial | 1/1 / 0/1 / 1/1 | 1 / 0 / 0 | 0 | - | FAIL / no patch / pass |
| cellar_pump_hyst | missing_hysteresis | partial / fixed / fixed | 1/1 / 1/1 / 1/1 | 1 / 0 / 0 | 1 | - | pass / pass / pass |
| cooler_ok | correct | partial / clean / clean | - / - / - | 1 / 0 / 0 | 0 | - | pass / no patch / no patch |
| drip_scheduler_u8 | millis_rollover | partial / clean / partial | 1/1 / 0/1 / 1/1 | 1 / 0 / 1 | 1 | a1,a3 | pass / no patch / pass |
| foyer_lamp_debounce | missing_debounce | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| glue_solenoid_short | timed_pulse_length | partial / clean / clean | 1/1 / 0/1 / 0/1 | 0 / 0 / 0 | 1 | - | pass / no patch / no patch |
| greenhouse_dual | missing_hysteresis, missing_failsafe | fixed / fixed / fixed | 2/2 / 2/2 / 2/2 | 0 / 0 / 1 | 0 | a1 | pass / pass / pass |
| greenhouse_ok | correct | clean / clean / fixed | - / - / - | 0 / 0 / 1 | 0 | a2 | no patch / no patch / pass |
| hoist_estop_invert | inverted_pullup | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 1 | - | pass / pass / pass |
| hold_to_arm_late | off_by_one_timing | partial / clean / clean | 1/1 / 0/1 / 0/1 | 0 / 0 / 0 | 1 | - | pass / no patch / no patch |
| inject_pulse_short | off_by_one_timing | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| kiln_door_block | blocking_delay | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| lab_ph_ok | correct | partial / clean / clean | - / - / - | 2 / 0 / 0 | 2 | - | pass / no patch / no patch |
| laundry_cycle_stuck | stuck_state_machine | fixed / partial / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| laundry_ok | correct | fixed / clean / clean | - / - / - | 1 / 0 / 0 | 1 | - | pass / no patch / no patch |
| lobby_lamp_ok | correct | clean / clean / clean | - / - / - | 0 / 0 / 0 | 0 | - | no patch / no patch / no patch |
| lock_ok | correct | partial / clean / clean | - / - / - | 1 / 0 / 0 | 2 | - | pass / no patch / no patch |
| loft_fan_ok | correct | partial / fixed / partial | - / - / - | 3 / 1 / 3 | 0 | - | pass / FAIL / pass |
| mist_injector_long | timed_pulse_length | partial / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| nav_beacon_byte_timer | millis_rollover | partial / partial / partial | 1/1 / 1/1 / 1/1 | 1 / 0 / 0 | 0 | - | FAIL / FAIL / FAIL |
| panel_dual_debounce_edge | missing_debounce, inverted_pullup | fixed / fixed / fixed | 1/2 / 1/2 / 1/2 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| porch_gate_block | blocking_delay | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| process_dual_block_scale | wrong_unit_scaling, blocking_delay | fixed / partial / partial | 2/2 / 2/2 / 2/2 | 0 / 1 / 2 | 0 | - | pass / pass / pass |
| rail_limit_invert | inverted_pullup | fixed / clean / clean | 1/1 / 0/1 / 0/1 | 0 / 0 / 0 | 1 | - | pass / no patch / no patch |
| shop_estop_debounce | missing_debounce | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |
| solenoid_ok | correct | partial / clean / clean | - / - / - | 1 / 0 / 0 | 0 | - | pass / no patch / no patch |
| spindle_rpm_prefix | serial_format | partial / fixed / fixed | 1/1 / 1/1 / 1/1 | 2 / 0 / 0 | 2 | - | pass / pass / pass |
| studio_siren_ok | correct | clean / clean / clean | - / - / - | 0 / 0 / 0 | 0 | - | no patch / no patch / no patch |
| vault_lock_stuck | stuck_state_machine | partial / clean / clean | 1/1 / 0/1 / 0/1 | 0 / 0 / 0 | 2 | - | pass / no patch / no patch |
| walk_in_cooler_failsafe | missing_failsafe | partial / fixed / fixed | 1/1 / 1/1 / 1/1 | 1 / 0 / 0 | 0 | - | pass / pass / pass |
| weather_line_prefix | serial_format | partial / fixed / partial | 1/1 / 1/1 / 1/1 | 2 / 0 / 1 | 1 | - | pass / pass / pass |
| weather_ok | correct | partial / clean / partial | - / - / - | 2 / 0 / 1 | 1 | - | pass / no patch / pass |
| workshop_kpa_scale | wrong_unit_scaling | fixed / fixed / fixed | 1/1 / 1/1 / 1/1 | 1 / 1 / 0 | 0 | - | pass / pass / pass |
| yard_relay_miswire | wrong_pin | partial / partial / partial | 1/1 / 1/1 / 1/1 | 0 / 0 / 0 | 0 | - | pass / pass / pass |

## What to do next

1. **Search:** it found no new real bug and 3 of its 4 findings sit on checks that fail on the reference. Options: report a search finding only if the check also passes on the clean rooms in every variant that breaks it (not on 12 sampled ones), require two variants to break it, or switch the search off until v3 has a case that needs it. The `greenhouse_ok` case also points at the evaluator: a toggle limit that no firmware can meet when the input swings fast should not fail.
2. **Correlated clean rooms:** ask the second clean room for a deliberately different reading of ambiguous bullets, or add a pass that has the model list the spec's ambiguous bullets first. This is the only route to `glue_solenoid_short` and `rail_limit_invert`.
3. **Time:** two rooms plus search put the median at 1.63x the first run. Judge the search's worth against that.

Files: `bench/results/dev_full2_20261115T222332Z_{hexorcist,score,replay}.json`, `dev_full_20261115T091310Z_*`, `v2_full_20261115T003855Z_*`, `bench/dev_compare.py`, `bench/replay_run.py`.
