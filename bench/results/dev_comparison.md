# DEV-set comparison, five runs

**DEV-set results.** Benchmark v2 has been seen and is now tuned on, on purpose. These numbers show whether the changes work. They are not evidence about unseen firmware: that needs the held-out v3 set, which does not exist yet. One run per case per column, so a difference of a few cases is within run-to-run noise. Every run also regenerates the checks from the spec, so a case can change result with no change in the agent.

| Column | Run | Agent |
| --- | --- | --- |
| old | `v2_full_20261115T003855Z` | the first benchmark: no cross-check, no search |
| one room | `dev_full_20261115T091310Z` | evaluator fix, one clean-room sketch (dropped if it fails the check in 50% of scenarios), spec grounding, search |
| two rooms | `dev_full2_20261115T222332Z` | two independent clean-room sketches from DeepSeek, a check is dropped only if both fail it the same way in at least 80% of the scenarios where the uploaded sketch fails it; same search |
| mixed rooms | `dev_full3_20261116T081621Z` | same rule, but room 1 is `deepseek-chat` and room 2 is `gpt-4o-mini`; search off (its acceptance gates were not exercised) |
| gate | `dev_full4_20261117T030319Z` | mixed rooms, plus the requirement gate (checks that ask for more than their spec bullet are left out) and clean rooms written only after a check fails; search off |

Same 40 frozen cases, same gpt-4o-mini judge, same frozen checks. The agent model is `deepseek-chat` in every run. Cost is the Hexorcist cost of each run (judge extra, about $0.006).

## Fifth run: requirement gate and lazy clean rooms (`dev_full4_20261117T030319Z`)

Same mixed rooms as the fourth run, plus the requirement gate (`backend/app/requirements.py`: checks that ask for more than the spec bullet they quote are left out of bugs, fixes and verification) and clean rooms written only after a check fails. Search off. 40 cases, one run each, so a difference of a few cases is within noise, and the checks are regenerated every run.

### Verdict

**False alarms dropped without losing recall or honest recall: strict false alarms 14 (fourth run) and 12 (two rooms) became 6, class B 11 became 5, recall went from 27/32 to 29/32 and honest recall from 26/32 to 27/32.** Only part of that is the gate.

- **Recall.** 29/32 (91%). Missed: `glue_solenoid_short`, `hold_to_arm_late` and the second bug of `panel_dual_debounce_edge`. Everything the fourth run detected is still detected, and `bench_led_miswire` and `vault_lock_stuck` are back. The gate left nothing out in those two cases, so those two are run-to-run variation, not a gate effect.
- **Honest recall.** 27/32 (84%). Two detections are hollow (matched only through a check that fails identically on the reference): `drip_scheduler_u8` and `vault_lock_stuck`. `nav_beacon_byte_timer` is honest this time and `drip_scheduler_u8` is not, which cancel; `bench_led_miswire` is the +1.
- **False alarms.** 4 on buggy cases (0.14 per case) and 2 on correct ones (0.18 per case). Eleven of the fourth run's 14 are gone and 3 are new. Six of the 11 are the same threshold-lamp checks the gate left out this time, two each in `weather_ok`, `weather_line_prefix` and `lab_ph_ok` (check ids differ from run to run). The other 5 (`bench_led_miswire` a1, `cabin_heater_mul_ovf` a2, `laundry_cycle_stuck` a1, `process_dual_block_scale` a1, `workshop_kpa_scale` a3) disappeared in cases where the gate left nothing out, so I count them as regeneration noise, not as the gate. The same six showed up as removed in the 10-case smoke run, which is the evidence that the gate effect is real.
- **Verified fix** on the frozen checks 25/29 (86%), and all 20 `fixed` claims pass them. Correct sketches given a patch: 1 (`loft_fan_ok`), none broken.
- **Cost** $0.195 for 40 runs (DeepSeek $0.183, OpenAI $0.012), median 109 s per case (1.09x the first run), 79 min in total, with the search off.

### Checks left out: 9 in 6 cases

| Case | Left out | Rule | Fails on the sketch / on the reference |
| --- | --- | --- | --- |
| weather_ok (correct) | a3, a4 | range_bound | 13 / 13, 8 / 8 scenarios |
| weather_line_prefix | a3, a4 | range_bound | 13 / 13, 6 / 6 |
| lab_ph_ok (correct) | a3, a4 | range_bound | 11 / 11, 9 / 9 |
| attic_vent_hyst | a2 | invented_converse | 15 / 12 |
| yard_relay_miswire | a2 | invented_converse | 4 / 19 |
| loft_fan_ok (correct) | a2 | invented_converse | 0 / 0 |

- **How many pass on the reference: 1 of 9.** It is `loft_fan_ok` a2, which failed on neither the sketch nor the reference, so leaving it out changed nothing. The other 8 fail on the reference (rightly left out). No check that fails the sketch and passes the reference, the kind that would be a real check wrongly removed, was left out.
- No detection depended on a left-out check: all six cases keep what they detected (`attic_vent_hyst` and `weather_line_prefix` moved from `partial` to `fixed`).
- `weather_ok` and `lab_ph_ok` became `clean` with no patch for a correct sketch, in both cases down from 2 false alarms to 0.

### The 6 remaining false alarms

| Case | Check | Class | Group | Why the gate does not touch it |
| --- | --- | --- | --- | --- |
| aquarium_ph_scale | a3 output_follows | not B | from its title, restates the planted bug | the reference fails it in only 11% of the scenarios, so it says something real |
| blend_tank_sum_ovf | a2 serial_period | B | G4 | spec-stated print period the reference misses under button activity |
| loft_fan_ok | a1 output_follows | B | G6 | boost bullet overrides the thresholds, check not suspended |
| loft_fan_ok | a3 max_toggles | B | G3 | spec-stated toggle limit that button bounce breaks on any firmware |
| nav_beacon_byte_timer | a1 output_follows | B | G2 | forcing bullet ("force the beacon OFF"), check also demands HIGH for the released input; **the gate should have caught this and did not**, see below |
| spindle_rpm_prefix | a3 output_follows | B | G2 | "while mute is released" is dropped from the check; that is the `dropped_condition` rule that was removed |

- The `nav_beacon_byte_timer` miss is a flaw in the gate: `invented_converse` accepts any bullet that contains the word "off" as having a converse, and this bullet's forced state is OFF. Taking "off" out of that word list would catch it. I have not made that change or run it.
- The five class B false alarms are all in groups the gate does not cover, or covers only partly. A real fix for G3, G4 and G6 is in the evaluator, not in the text of the check.

### Run audit

| Check | Result |
| --- | --- |
| Rows with mixed rooms and no fallback | 40 of 40 |
| Cases where the cross-check ran | 33, with room 2 `ready` on `gpt-4o-mini` at `api.openai.com` in all 33 |
| Cases where the cross-check was not needed | 7 (`cooler_ok`, `greenhouse_ok`, `lab_ph_ok`, `lobby_lamp_ok`, `solenoid_ok`, `studio_siren_ok`, `weather_ok`): no clean-room call, $0 OpenAI in every one (the fourth run billed 6 of them) |
| Rows with an error | none |
| Search variants run | 0 |
| Unconfirmed checks | 15 in 11 cases: 14 fail on the reference (rightly dropped), 1 passes (`glue_solenoid_short` a1, a real check wrongly dropped, as in the two previous runs) |


## Verdict on the fourth run (mixed rooms)

**Model diversity recovered `rail_limit_invert` but not `glue_solenoid_short`, and false alarms went up, not down: 14 strict, against 12 in the two-room run (10 without the two the search produced) and 6 in the one-room run.**

- `rail_limit_invert` is detected and fixed (frozen checks pass). Its check was kept, so the two-room rule no longer dropped it.
- `glue_solenoid_short` is still missed. Both rooms, including the `gpt-4o-mini` one, failed `a1` (`timed_pulse`) in 13 of the 14 scenarios where the uploaded sketch fails, with near-identical evidence ("pulse from 1.03 s was still on after 6968 ms" and "after 6967 ms"). The reference passes that check, so a real check was dropped, as in the two-room run. A second model did not give a second opinion here.
- `bench_led_miswire` was lost (found in the two-room run, missed now). Its reported check `a1` fails on the reference in 7 scenarios, which is 64% of the scenarios where it fails on the sketch, so it is a class B false alarm and the judge did not match it to the planted bug. One run cannot separate this from noise.
- Recall is 27/32, the same as the two-room run. Honest recall is **26/32**, up from 25 and equal to the first run. The only hollow detection left is `nav_beacon_byte_timer`.
- Strict false alarms: 9 on buggy cases and 5 on correct ones. Of the 14, 11 sit on checks that also fail on the known-good reference (class B). Nine are new against the two-room run and seven are gone. I did not test why: that a weaker second model writes rooms that fail the checks less often than DeepSeek's rooms is a hypothesis.
- Verified fix on the frozen checks is 23/29 (79%), against 24/29 in the two-room run. Every one of the 17 `fixed` claims passes the frozen checks.
- Cost is $0.215 for 40 runs (DeepSeek $0.201, OpenAI $0.014). Median time per case is 114 s, 1.14x the first run, with the search off.

## Run audit of the fourth run: did room 2 really run on gpt-4o-mini?

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

| Metric | old | one room | two rooms | mixed rooms | gate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Detection recall (32 bugs) | 31/32 (97%) | 24/32 (75%) | 27/32 (84%) | 27/32 (84%) | 29/32 (91%) |
| **Honest recall** (see below) | 26/32 (81%) | 22/32 (69%) | 25/32 (78%) | 26/32 (81%) | 27/32 (84%) |
| False alarms per buggy case, strict | 0.48 (14) | 0.17 (5) | 0.24 (7) | 0.31 (9) | 0.14 (4) |
| False alarms per correct case, strict | 1.18 (13) | 0.09 (1) | 0.45 (5) | 0.45 (5) | 0.18 (2) |
| Verified fix on buggy cases (frozen checks) | 27/29 (93%) | 21/29 (72%) | 24/29 (83%) | 23/29 (79%) | 25/29 (86%) |
| Own status `fixed` | 15 | 17 | 18 | 17 | 20 |
| Fixed-claim precision (claims whose patch passes the frozen checks) | 15/15 | 16/17 | 18/18 | 17/17 | 20/20 |
| Statuses clean / fixed / partial | 3 / 15 / 22 | 17 / 17 / 6 | 12 / 18 / 10 | 11 / 17 / 12 | 12 / 20 / 8 |
| Correct sketches given a patch (of 11) | 8 | 1 | 3 | 3 | 1 |
| Correct sketch broken by its patch | 0 | 1 | 0 | 0 | 0 |
| Unconfirmed checks (cases) | n/a | 27 (16) | 20 (16) | 17 (12) | 15 (11) |
| ...of which fail on the reference too (rightly dropped) | n/a | 25 | 18 | 16 | 14 |
| ...of which pass on the reference (real checks wrongly dropped) | n/a | 2 | 2 | 1 | 1 |
| Ungrounded checks left out (cases) | n/a | n/a | n/a | n/a | 9 (6) |
| ...of which fail on the reference (rightly left out) | n/a | n/a | n/a | n/a | 8 |
| ...of which pass on the reference | n/a | n/a | n/a | n/a | 1 (`loft_fan_ok` a2, failed nowhere) |
| Bugs found by search | n/a | 0 | 4 | 0 (search off) | 0 (search off) |
| Cost of the 40 runs | $0.241 | $0.165 | $0.208 | $0.215 (DeepSeek $0.201, OpenAI $0.014) | $0.194 (DeepSeek $0.182, OpenAI $0.012) |
| Median time per case | 100 s | 115 s | 164 s | 114 s | 109 s |
| Total time | 70 min | 88 min | 118 min | 85 min | 79 min |

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

## Why the class B false alarms fail on the reference (dev_full, dev_full2, dev_full3)

All 22 class B false alarms of the three dev runs, with the check behind each report. The reference replay says the reference fails them in at least half of the scenarios where the uploaded sketch does. The report title ("chatters", "no hysteresis") is the diagnosis step's wording of the failing evidence. The check itself is something else, as the table shows.

**None of the 22 checks invents a hysteresis, debounce or rate-limit requirement.** In all 22 the check's `spec_quote` is a verbatim spec bullet (word overlap 1.0 with the bullet it names, found by `grounding.find_quote`), and every threshold and limit in the check is in the spec text (21 of 22 in the quoted bullet itself; the 120 ms tolerance of `drip_scheduler_u8` a3 comes from the adjacent period bullet). Hysteresis, chatter and debounce appear in the titles only. So a gate that asks "does the spec ask for hysteresis, debounce or a toggle limit" would have removed none of them. What the 22 do share is that the check says more, or something different, than its bullet. Groups:

| Group | Root cause | Rows | Assertion types |
| --- | --- | ---: | --- |
| G1 | Half of a two-sided range, with an invented "otherwise" on the far side | 8 | output_follows |
| G2 | Invented converse, or a dropped condition | 3 | output_follows |
| G3 | Spec-stated rate limit that fast inputs force every firmware to break | 4 | max_toggles |
| G4 | Spec-stated print period that the reference itself misses under button activity | 4 | serial_period |
| G5 | Threshold edge timing | 2 | output_follows |
| G6 | Two bullets drive one output, the check ignores the other | 1 | output_follows |

- **G1.** The quote says "outside A to B". The assertion keeps one bound and says the output is LOW on the whole far side (`A0 >= -10` must be LOW), which is wrong above B. The reference fails it as soon as the input passes the other bound (ramp, extremes). Number of bounds in the quote: 2, in the assertion: 1.
- **G2.** The quote states one direction only ("force the fan ON", "force the heater ON regardless", "while D2 is pressed and D4 is released"). The assertion adds the opposite state (`D4 released -> OFF`) or drops the second input (`D4`), so it contradicts another bullet. Reference fails in every scenario where the other bullet applies.
- **G3.** The limit (2 changes in 5000 ms) is in the spec, word for word, and the assertion matches it. It fails on the reference in scenarios where the button or the temperature itself demands more changes (bounce, rapid presses, rapid oscillation).
- **G4.** Period and tolerance are in the spec and match. The reference prints late while the button is bounced, held or floating (worst gap 1.2 to 2.5 s) or, for `drip_scheduler_u8`, in a 1.6 s search scenario that cannot hold a 1600 ms line.
- **G5.** Threshold and polarity match the spec. The reference differs from the injected value by up to a few hundred ms right at 90 kPa (ramp, spike, crossing). I did not trace the exact mechanism (ADC rounding or sampling instant).
- **G6.** Hysteresis thresholds 36/32 match the spec exactly. The reference fails only in the 3 scenarios where the D4 boost bullet is active, because the check is not suspended while the boost forces the fan ON.

Rows (the quote equals the bullet in every row; reference share is the share of the sketch-failing scenarios where the reference also fails):

| Group | Run | Case | Check | Type | Spec bullet = `spec_quote` | Thresholds and limits in the check | Ref. share |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| G1 | dev_full2 | weather_line_prefix | a4 | output_follows | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | high A0<-10, low A0>=-10, within_ms=500 | 100% |
| G1 | dev_full2 | weather_ok (correct) | a4 | output_follows | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | high A0<-10, low A0>=-10, within_ms=500 | 100% |
| G1 | dev_full3 | lab_ph_ok (correct) | a3 | output_follows | Drive D10 HIGH when pH is outside 6.50–8.50 inclusive; otherwise LOW. | high A1<6.5, low A1>=6.5, within_ms=500 | 100% |
| G1 | dev_full3 | lab_ph_ok (correct) | a4 | output_follows | Drive D10 HIGH when pH is outside 6.50–8.50 inclusive; otherwise LOW. | high A1>8.5, low A1<=8.5, within_ms=500 | 100% |
| G1 | dev_full3 | weather_line_prefix | a4 | output_follows | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | high A0>50, low A0<=50, within_ms=500 | 100% |
| G1 | dev_full3 | weather_line_prefix | a5 | output_follows | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | high A0<-10, low A0>=-10, within_ms=500 | 100% |
| G1 | dev_full3 | weather_ok (correct) | a3 | output_follows | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | high A0<-10, low A0>=-10, within_ms=500 | 100% |
| G1 | dev_full3 | weather_ok (correct) | a4 | output_follows | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | high A0>50, low A0<=50, within_ms=500 | 100% |
| G2 | dev_full2 | loft_fan_ok (correct) | a2 | output_follows | While D4 is held LOW, force the fan ON. | high D4==0, low D4==1, within_ms=500 | 100% |
| G2 | dev_full3 | bench_led_miswire | a1 | output_follows | While D2 is pressed and D4 is released, light D13 HIGH; release turns D13 LOW. | high D2==0, low D2==1, within_ms=100 | 64% |
| G2 | dev_full3 | cabin_heater_mul_ovf | a2 | output_follows | While D2 is held LOW, force the heater ON regardless of temperature. | high D2==0, low D2==1, within_ms=600 | 100% |
| G3 | dev_full_ | loft_fan_ok (correct) | a3 | max_toggles | Fan must not change state more than 2 times in any 5000 ms window. | max_toggles=2, window_ms=5000 | 100% |
| G3 | dev_full2 | greenhouse_ok (correct) | a2 | max_toggles | Fan must not change state more than 2 times in any 5000 ms window. | max_toggles=2, window_ms=5000 | 100% |
| G3 | dev_full2 | loft_fan_ok (correct) | a3 | max_toggles | Fan must not change state more than 2 times in any 5000 ms window. | max_toggles=2, window_ms=5000 | 100% |
| G3 | dev_full3 | loft_fan_ok (correct) | a3 | max_toggles | Fan must not change state more than 2 times in any 5000 ms window. | max_toggles=2, window_ms=5000 | 100% |
| G4 | dev_full_ | blend_tank_sum_ovf | a2 | serial_period | Lines matching `pct: ` must appear every 1000 ms ±150 ms. | period_ms=1000, tolerance_ms=150 | 100% |
| G4 | dev_full2 | blend_tank_sum_ovf | a2 | serial_period | Lines matching `pct: ` must appear every 1000 ms ±150 ms. | period_ms=1000, tolerance_ms=150 | 100% |
| G4 | dev_full2 | drip_scheduler_u8 | a3 | serial_period | Every 1600 ms print `drip n=<count> pause=<0\|1>`. | period_ms=1600, tolerance_ms=120 | 100% |
| G4 | dev_full3 | blend_tank_sum_ovf | a2 | serial_period | Lines matching `pct: ` must appear every 1000 ms ±150 ms. | period_ms=1000, tolerance_ms=150 | 100% |
| G5 | dev_full_ | workshop_kpa_scale | a3 | output_follows | Drive D12 HIGH when pressure is at or above 90.0 kPa; otherwise LOW. | high A2>=90, low A2<90, within_ms=500 | 62% |
| G5 | dev_full3 | workshop_kpa_scale | a3 | output_follows | Drive D12 HIGH when pressure is at or above 90.0 kPa; otherwise LOW. | high A2>=90, low A2<90, within_ms=500 | 60% |
| G6 | dev_full2 | loft_fan_ok (correct) | a1 | output_follows | Turn the fan ON at 36.0 °C or above; turn it OFF at 32.0 °C or below. | high A3>=36, low A3<=32, within_ms=500 | 100% |

What this means for a gate: G1 and G2 (11 rows) are checks whose structure goes beyond the bullet, and a deterministic comparison of the quote with the assertion can catch them (bounds in the quote versus bounds in the check, an opposite state the quote never states, an input named in the quote and absent from the check). G3 to G6 (11 rows) are faithful to the spec and fail on the reference for evaluator or scenario reasons, so no text gate can touch them.

## Requirement gate: offline sweep over the stored dev assertions

`backend/app/requirements.py` marks a check "ungrounded requirement" when it asks for more than the spec bullet it quotes, and leaves it out of bugs, the fix loop and verification (it still runs and is shown in the report). I applied it, without any LLM or sandbox call, to the stored assertions of the three dev runs. These are the same runs the rules were designed from, so this shows what the rules do on this set, not on unseen specs.

| Rule | What it marks | dev_full | dev_full2 | dev_full3 |
| --- | --- | ---: | ---: | ---: |
| `range_bound` | "outside A to B" kept as one bound plus an "otherwise" on the far side (G1) | 6 | 6 | 6 |
| `invented_converse` | a forcing bullet ("force the fan ON") checked for the released input too (G2) | 2 | 2 | 3 |
| `rate_limit`, `hysteresis_band`, `debounce` | a toggle limit, a threshold band or a settle time the bullet does not state | 0 | 0 | 0 |
| Assertions marked / all | | 8 / 188 | 8 / 188 | 9 / 192 |
| Class B false alarms removed | | 0 | 3 | 7 |
| Planted bugs left with no surviving matched check | | 0 | 0 | 0 |

- In dev_full3 the 14 strict false alarms would have been 7 (the 7 removed are `weather_ok` a3 and a4, `weather_line_prefix` a4 and a5, `lab_ph_ok` a3 and a4, `cabin_heater_mul_ovf` a2). Left: `bench_led_miswire` a1, `blend_tank_sum_ovf` a2, `loft_fan_ok` a3, `workshop_kpa_scale` a3 (class B), plus the 3 not-B ones. Apart from `bench_led_miswire` (G2, see the removed rule below), those are G3 to G5: faithful to the spec, failing on the reference for evaluator or scenario reasons. A text gate cannot reach them.
- The three behaviour-quality rules (toggle limit, band, debounce) mark nothing in 568 stored assertions, because every bullet in these specs states what its check asks for. They guard against invented chatter, hysteresis and debounce checks for specs that do not state them, and none of the 22 false alarms was one.
- Marked checks that were already `unconfirmed` or reported as a duplicate of a planted bug (`yard_relay_miswire` a2) change nothing in the score.
- A rule that marks a check whose quote names two input pins while the check uses one (`dropped_condition`) was tried and removed. It would have removed `bench_led_miswire` a1 in dev_full3 (a class B false alarm), and in dev_full2 the same check was the only one matched to the planted bug, so it cost a real detection.
- Limit of the sweep: stored assertions carry every default, so the debounce rule's "only when the model chose the settle time" test could not be replayed. The smoke run below exercises it.

## Requirement gate: smoke run on 10 cases (`dev_gate_smoke_20261117T002104Z`)

The four cases with threshold-lamp and fan false alarms, plus every case whose planted bug is `missing_hysteresis` or `missing_debounce`, run with the gate on and the clean rooms written only after a failure. Compared with the same cases in dev_full3. One run each, so single-case moves are within noise. Cost $0.049 (DeepSeek $0.046, OpenAI $0.003) plus $0.002 for the judge.

| Case | Status old / new | Detected old / new | False alarms old / new | Checks left out |
| --- | --- | --- | --- | ---: |
| weather_ok (correct) | partial / clean | - | 2 / 0 | 2 |
| weather_line_prefix | partial / fixed | 1/1 / 1/1 | 2 / 0 | 2 |
| lab_ph_ok (correct) | partial / clean | - | 2 / 0 | 2 |
| loft_fan_ok (correct) | partial / partial | - | 1 / 2 | 1 |
| attic_vent_hyst | partial / fixed | 1/1 / 1/1 | 0 / 0 | 1 |
| cellar_pump_hyst | fixed / partial | 1/1 / 1/1 | 0 / 1 | 0 |
| foyer_lamp_debounce | fixed / fixed | 1/1 / 1/1 | 0 / 0 | 0 |
| greenhouse_dual | fixed / fixed | 2/2 / 2/2 | 0 / 0 | 0 |
| panel_dual_debounce_edge | fixed / fixed | 1/2 / 1/2 | 0 / 0 | 0 |
| shop_estop_debounce | fixed / fixed | 1/1 / 1/1 | 0 / 0 | 0 |

- **Real hysteresis and debounce bugs are still caught.** All six cases keep their detections: 8 of 9 planted bugs, all 8 honest (the failing check passes on the reference somewhere). The one miss, the `inverted_pullup` bug in `panel_dual_debounce_edge`, was missed in all four earlier runs. None of the left-out checks was behind a detection.
- **The three threshold-lamp cases lose all 6 false alarms.** Each left-out check (`weather_ok` a3 and a4, `weather_line_prefix` a3 and a4, `lab_ph_ok` a3 and a4) is a `range_bound` check that fails on the reference in every scenario where it fails on the sketch. `weather_ok` and `lab_ph_ok` are now `clean` with no patch written for a correct sketch.
- **`loft_fan_ok` went from 1 false alarm to 2.** `a3` (the spec's own 2-changes-per-5000-ms limit, broken by button bounce on the reference too, group G3) is back, and `a1` ("fan stays ON after boost release") is new: it fails on the reference in 1 scenario (group G6, the boost bullet overriding the thresholds). The gate cannot reach either.
- **`cellar_pump_hyst` gained a false alarm,** `a5`, a printed-level tolerance of ±0.1 cm that the reference also fails in 7 scenarios. Nothing to do with the gate: it makes the status `partial`.
- **Left-out checks, by the reference replay:** 7 of 8 fail on the reference (rightly left out). One passes on it: `loft_fan_ok` a2 (`invented_converse`), which failed on neither the sketch nor the reference in this run, so leaving it out changed no result. A real check that was wrongly removed would show as passing on the reference and failing on the sketch. None did.
- `attic_vent_hyst` a2 (`invented_converse`, 14 failing scenarios on the sketch, 12 on the reference) was left out. The status moved from `partial` to `fixed`, and the planted bug was found through `a1` and `a3`.
- **Clean rooms:** `weather_ok` and `lab_ph_ok` were `not_needed` and made no clean-room call (room 2 calls 0, OpenAI cost $0). The other eight ran both rooms on `deepseek-chat` and `gpt-4o-mini`, with no skips.

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

## Per case (old / one room / two rooms / mixed rooms / gate)

Unconfirmed is "two rooms / mixed rooms / gate". Left out is the gate run's checks that ask for more than their spec bullet.

| Case | Category | Status | Detected | False alarms | Unconfirmed | Left out (gate) | Frozen checks on the patch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aquarium_ph_scale | wrong_unit_scaling | fixed / partial / fixed / partial / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 1 / 1 / 1 / 1 | 0 / 1 / 0 | - | pass / pass / pass / pass / pass |
| attic_vent_hyst | missing_hysteresis | partial / partial / partial / partial / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 1 / 1 / 0 / 0 / 0 | 0 / 1 / 1 | a2 | pass / pass / pass / pass / pass |
| bench_led_miswire | wrong_pin | partial / clean / partial / partial / fixed | 1/1 / 0/1 / 1/1 / 0/1 / 1/1 | 0 / 0 / 0 / 1 / 0 | 1 / 1 / 1 | - | pass / no patch / pass / pass / pass |
| blend_tank_sum_ovf | integer_overflow | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| boiler_ok | correct | partial / clean / clean / clean / clean | - / - / - / - / - | 2 / 0 / 0 / 0 / 0 | 1 / 0 / 2 | - | pass / no patch / no patch / no patch / no patch |
| boiler_valve_failsafe | missing_failsafe | partial / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 2 / 0 / 0 / 0 / 0 | 1 / 2 / 2 | - | pass / pass / pass / pass / pass |
| cabin_heater_mul_ovf | integer_overflow | partial / clean / partial / partial / partial | 1/1 / 0/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 1 / 0 | 0 / 0 / 0 | - | FAIL / no patch / pass / FAIL / pass |
| cellar_pump_hyst | missing_hysteresis | partial / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 0 / 0 | 1 / 1 / 1 | - | pass / pass / pass / pass / pass |
| cooler_ok | correct | partial / clean / clean / clean / clean | - / - / - / - / - | 1 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / no patch / no patch / no patch / no patch |
| drip_scheduler_u8 | millis_rollover | partial / clean / partial / partial / partial | 1/1 / 0/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 1 / 0 / 0 | 1 / 2 / 2 | - | pass / no patch / pass / FAIL / FAIL |
| foyer_lamp_debounce | missing_debounce | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| glue_solenoid_short | timed_pulse_length | partial / clean / clean / clean / clean | 1/1 / 0/1 / 0/1 / 0/1 / 0/1 | 0 / 0 / 0 / 0 / 0 | 1 / 1 / 1 | - | pass / no patch / no patch / no patch / no patch |
| greenhouse_dual | missing_hysteresis, missing_failsafe | fixed / fixed / fixed / fixed / fixed | 2/2 / 2/2 / 2/2 / 2/2 / 2/2 | 0 / 0 / 1 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| greenhouse_ok | correct | clean / clean / fixed / clean / clean | - / - / - / - / - | 0 / 0 / 1 / 0 / 0 | 0 / 0 / 0 | - | no patch / no patch / pass / no patch / no patch |
| hoist_estop_invert | inverted_pullup | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 1 / 0 / 0 | - | pass / pass / pass / pass / pass |
| hold_to_arm_late | off_by_one_timing | partial / clean / clean / clean / clean | 1/1 / 0/1 / 0/1 / 0/1 / 0/1 | 0 / 0 / 0 / 0 / 0 | 1 / 1 / 1 | - | pass / no patch / no patch / no patch / no patch |
| inject_pulse_short | off_by_one_timing | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| kiln_door_block | blocking_delay | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| lab_ph_ok | correct | partial / clean / clean / partial / clean | - / - / - / - / - | 2 / 0 / 0 / 2 / 0 | 2 / 0 / 0 | a3, a4 | pass / no patch / no patch / pass / no patch |
| laundry_cycle_stuck | stuck_state_machine | fixed / partial / fixed / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 1 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| laundry_ok | correct | fixed / clean / clean / clean / clean | - / - / - / - / - | 1 / 0 / 0 / 0 / 0 | 1 / 1 / 1 | - | pass / no patch / no patch / no patch / no patch |
| lobby_lamp_ok | correct | clean / clean / clean / clean / clean | - / - / - / - / - | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | no patch / no patch / no patch / no patch / no patch |
| lock_ok | correct | partial / clean / clean / clean / clean | - / - / - / - / - | 1 / 0 / 0 / 0 / 0 | 2 / 2 / 2 | - | pass / no patch / no patch / no patch / no patch |
| loft_fan_ok | correct | partial / fixed / partial / partial / partial | - / - / - / - / - | 3 / 1 / 3 / 1 / 2 | 0 / 0 / 0 | a2 | pass / FAIL / pass / pass / pass |
| mist_injector_long | timed_pulse_length | partial / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| nav_beacon_byte_timer | millis_rollover | partial / partial / partial / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 0 / 1 | 0 / 0 / 0 | - | FAIL / FAIL / FAIL / FAIL / FAIL |
| panel_dual_debounce_edge | missing_debounce, inverted_pullup | fixed / fixed / fixed / fixed / fixed | 1/2 / 1/2 / 1/2 / 1/2 / 1/2 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| porch_gate_block | blocking_delay | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| process_dual_block_scale | wrong_unit_scaling, blocking_delay | fixed / partial / partial / fixed / fixed | 2/2 / 2/2 / 2/2 / 2/2 / 2/2 | 0 / 1 / 2 / 1 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| rail_limit_invert | inverted_pullup | fixed / clean / clean / fixed / fixed | 1/1 / 0/1 / 0/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 1 / 0 / 0 | - | pass / no patch / no patch / pass / pass |
| shop_estop_debounce | missing_debounce | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| solenoid_ok | correct | partial / clean / clean / clean / clean | - / - / - / - / - | 1 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / no patch / no patch / no patch / no patch |
| spindle_rpm_prefix | serial_format | partial / fixed / fixed / fixed / partial | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 2 / 0 / 0 / 0 / 1 | 2 / 2 / 1 | - | pass / pass / pass / pass / pass |
| studio_siren_ok | correct | clean / clean / clean / clean / clean | - / - / - / - / - | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | no patch / no patch / no patch / no patch / no patch |
| vault_lock_stuck | stuck_state_machine | partial / clean / clean / clean / partial | 1/1 / 0/1 / 0/1 / 0/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 2 / 2 / 0 | - | pass / no patch / no patch / no patch / pass |
| walk_in_cooler_failsafe | missing_failsafe | partial / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 1 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| weather_line_prefix | serial_format | partial / fixed / partial / partial / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 2 / 0 / 1 / 2 / 0 | 1 / 0 / 0 | a3, a4 | pass / pass / pass / pass / pass |
| weather_ok | correct | partial / clean / partial / partial / clean | - / - / - / - / - | 2 / 0 / 1 / 2 / 0 | 1 / 0 / 0 | a3, a4 | pass / no patch / pass / pass / no patch |
| workshop_kpa_scale | wrong_unit_scaling | fixed / fixed / fixed / fixed / fixed | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 1 / 1 / 0 / 1 / 0 | 0 / 0 / 0 | - | pass / pass / pass / pass / pass |
| yard_relay_miswire | wrong_pin | partial / partial / partial / partial / partial | 1/1 / 1/1 / 1/1 / 1/1 / 1/1 | 0 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | a2 | pass / pass / pass / pass / pass |

## What to do next

1. **Gate:** take "off" out of the converse word list of `invented_converse` (it let `nav_beacon_byte_timer` a1 through), then re-run the six cases that still have an `output_follows` false alarm. Decide separately whether to bring back the `dropped_condition` rule: it would remove `spindle_rpm_prefix` a3 and, on the stored runs, cost one real `bench_led_miswire` detection.
2. **Evaluator:** the remaining class B false alarms are G3 (toggle limit under forced input), G4 (print period under button activity) and G6 (two bullets on one output). None can be fixed in the text of the check.
3. **Missed bugs:** `glue_solenoid_short` (the check is dropped by both rooms as in every run since the cross-check was added), `hold_to_arm_late` and the second bug of `panel_dual_debounce_edge`.
4. **Noise:** run the gate configuration a second time before reading single-case moves, such as `bench_led_miswire` and `vault_lock_stuck`, as a trend.

Files: `bench/results/dev_full4_20261117T030319Z_{hexorcist,score,replay}.json`, `dev_full3_20261116T081621Z_*`, `dev_full2_20261115T222332Z_*`, `dev_full_20261115T091310Z_*`, `v2_full_20261115T003855Z_*`, `bench/dev_compare.py`, `bench/replay_run.py`.
