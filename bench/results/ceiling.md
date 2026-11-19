# Ceiling analysis: where Hexorcist and plain reading differ per planted bug

Analysis only. No code was changed, no LLM call and no benchmark run was made. Every number below was computed by script from stored files and the script asserted the totals against the score files: the plain-review judgements and scores (`v2_full_20261115T003855Z_score_deepseek` / `_openai`, `practice_baseline_deepseek_20261117_score` / `practice_baseline_openai_20261117_score`), Hexorcist `dev_full5_20261118T051737Z` on v2 and `dev_practice2_20261118T063831Z` on the practice set, with their score, replay and raw files. The per-scenario failures of each matched check come from the stored runs (`GET /api/runs/<id>` on the local stack, read only).

**Both sets are development sets that the agent was tuned on. These are one run per column, and checks are regenerated on every run, so a difference of one case is within noise.**

## How the columns are defined

- **Found by reading / by Hexorcist:** the judge (`gpt-4o-mini`) matched at least one report to that planted bug. This is the same detection the score files count (the script confirmed that the judgement files and the score files agree for all 39 bugs).
- **Hexorcist honest:** a report matched to the bug rests on a check that fails on the uploaded sketch in at least one scenario where the known-good reference passes. "no (hollow)" means the bug counts as found but every scenario where the matched check fails is one where the reference fails it too. "—" means not found.
- **Defensible** (section 4) is my reading of the judge matches: the matched report must name the planted cause, not just a symptom in the same area. This is a judgement, not something a script can check; I list every match I would not defend.

## Table: one row per planted bug

### v2, 32 bugs in 29 buggy cases

| Case | Bug | Planted bug | DeepSeek reading | gpt-4o-mini reading | Hexorcist | Hexorcist honest |
| --- | --- | --- | :-: | :-: | :-: | :-: |
| `aquarium_ph_scale` | b1 | Prints millivolts as pH instead of mv/500 | yes | yes | yes | yes |
| `attic_vent_hyst` | b1 | Single 42 C trip point chatters under sensor noise | yes | yes | yes | no (hollow) |
| `bench_led_miswire` | b1 | Drives D12 instead of D13 | yes | yes | yes | yes |
| `blend_tank_sum_ovf` | b1 | int accumulator of ADC samples overflows on AVR | yes | no | yes | yes |
| `boiler_valve_failsafe` | b1 | Valve stays open on sensor overrange | yes | yes | yes | yes |
| `cabin_heater_mul_ovf` | b1 | analogRead*5000 overflows 16-bit int before /1023 | yes | yes | yes | yes |
| `cellar_pump_hyst` | b1 | Single 45 cm start level short-cycles the pump | yes | yes | yes | yes |
| `drip_scheduler_u8` | b1 | uint8_t schedule and byte PERIOD_MS wrap, drip cadence too fast | yes | yes | yes | yes |
| `foyer_lamp_debounce` | b1 | Raw edge sampling multi-toggles through bounce | yes | yes | yes | yes |
| `glue_solenoid_short` | b1 | Solenoid pulse is 1 s not 2.5 s | yes | yes | yes | yes |
| `greenhouse_dual` | b1 | Single 28 C threshold chatters under hover noise | yes | yes | yes | yes |
| `greenhouse_dual` | b2 | Floating probe leaves fan off instead of fail-safe ON | yes | yes | yes | yes |
| `hoist_estop_invert` | b1 | E-stop polarity inverted vs pull-up wiring | yes | yes | yes | yes |
| `hold_to_arm_late` | b1 | Arm delay is 600 ms instead of 500 ms | yes | yes | no | — |
| `inject_pulse_short` | b1 | Pulse length 2000 ms instead of 3000 ms | yes | yes | yes | yes |
| `kiln_door_block` | b1 | delay(2000) freezes heartbeat and misses follow-up presses | yes | yes | yes | yes |
| `laundry_cycle_stuck` | b1 | RUN state never exits when level drops | yes | yes | yes | yes |
| `mist_injector_long` | b1 | Injector pulse 2 s instead of 800 ms | yes | yes | yes | yes |
| `nav_beacon_byte_timer` | b1 | byte HALF_MS truncates 500 to 244 so blink period is too short | yes | yes | yes | yes |
| `panel_dual_debounce_edge` | b1 | No settle window, bounce creates extra toggles | yes | yes | yes | yes |
| `panel_dual_debounce_edge` | b2 | Acts on release edge instead of press | yes | no | no | — |
| `porch_gate_block` | b1 | delay(1800) stalls heartbeat during chime | yes | yes | yes | yes |
| `process_dual_block_scale` | b1 | Treats raw ADC counts as L/h | yes | yes | yes | yes |
| `process_dual_block_scale` | b2 | delay(2000) stalls log cadence and responsiveness | yes | yes | yes | yes |
| `rail_limit_invert` | b1 | Treats pull-up HIGH as active limit | yes | yes | yes | yes |
| `shop_estop_debounce` | b1 | Immediate edge detect counts bounce as presses | yes | yes | yes | yes |
| `spindle_rpm_prefix` | b1 | Prints rpm: with space instead of RPM: | yes | yes | yes | yes |
| `vault_lock_stuck` | b1 | Lock latches forever after first engage | yes | no | yes | no (hollow) |
| `walk_in_cooler_failsafe` | b1 | No safe-OFF on floating/out-of-range probe | yes | yes | yes | yes |
| `weather_line_prefix` | b1 | Prints temp= instead of Temp:  | yes | no | yes | yes |
| `workshop_kpa_scale` | b1 | Omits 500 mV zero offset so kPa reads 50 high | yes | yes | yes | yes |
| `yard_relay_miswire` | b1 | Relay driven on D7 not D8 | yes | yes | yes | yes |

### Practice set, 7 bugs in 7 buggy cases

| Case | Bug | Planted bug | DeepSeek reading | gpt-4o-mini reading | Hexorcist | Hexorcist honest |
| --- | --- | --- | :-: | :-: | :-: | :-: |
| `cold_store_alarm` | b1 | The count of consecutive high samples is reset only by a sample at or below the clear level, so spikes between 8.0 and 12.0 C add up across time and eventually raise the alarm | yes | no | no | — |
| `door_chime_poll` | b1 | The button is polled every 30 ms and two consecutive low samples are required, so a 45 ms press is missed unless it happens to cover two samples | yes | no | yes | yes |
| `lift_call_panel` | b1 | The acknowledgement waits 300 ms inside delay(), so a heartbeat that falls due during it is printed up to 300 ms late; only presses that land shortly before a heartbeat show it | yes | yes | yes | yes |
| `orchard_spray_valve` | b1 | The close time is stored as an absolute millis() value, so a burst that starts within 400 ms of the 32-bit rollover closes at once | yes | yes | yes | no (hollow) |
| `silo_fill_gauge` | b1 | The running sum of 40 ADC readings is a 16-bit int, which overflows once the level is above about 4000 mm, so the printed level turns negative and the lamp never lights | yes | yes | yes | yes |
| `stair_light_timer` | b1 | Changing the mode switch while the light is on restarts the 3 s timer, so the light stays on longer than the press allows; the press and the mode switch are each correct on their own | yes | no | yes | yes |
| `tank_mixer_cycle` | b1 | The 16-bit clock is compared with absolute deadlines, so the schedule breaks whenever the clock wraps, every 65.5 s of uptime | yes | no | yes | no (hollow) |

Totals (script-checked): v2 DeepSeek 32/32, gpt-4o-mini 28/32, Hexorcist 30/32 (honest 28). Practice DeepSeek 7/7, gpt-4o-mini 3/7, Hexorcist 6/7 (honest 4). All 39 bugs together: DeepSeek 39, gpt-4o-mini 31, Hexorcist 36 (honest 32).

## Report

### 1. Bugs only plain reading finds (Hexorcist misses them)

**3 bugs**, all found by DeepSeek: `hold_to_arm_late` b1, `panel_dual_debounce_edge` b2, `cold_store_alarm` b1. Only `hold_to_arm_late` b1 is also found by gpt-4o-mini; the other two only by DeepSeek. Counting the two sets: 2 of 32 on v2, 1 of 7 on practice.

### 2. Bugs only Hexorcist finds (plain reading misses them)

**None.** DeepSeek found every bug Hexorcist found (and 3 more), so no bug is Hexorcist-only, and no bug was missed by both reading models and found by Hexorcist. Against gpt-4o-mini alone, Hexorcist found 6 bugs it missed (3 on v2, 3 on practice): `blend_tank_sum_ovf` b1, `vault_lock_stuck` b1, `weather_line_prefix` b1, `door_chime_poll` b1, `stair_light_timer` b1, `tank_mixer_cycle` b1. gpt-4o-mini found 1 that Hexorcist missed: `hold_to_arm_late` b1.

### 3. Bugs neither finds

**None.** All 39 planted bugs are found by at least one system as the judge matched them. This says nothing about how much of that is deep: 4 of the 36 Hexorcist detections are hollow (below).

Hexorcist's hollow detections (found, but not honest): `attic_vent_hyst` b1, `vault_lock_stuck` b1, `orchard_spray_valve` b1, `tank_mixer_cycle` b1.

### 4. Maximum recall gain a hypothesis pass could add

A hypothesis pass could at most recover the group 1 bugs that reading finds with a defensible match.

| Bug | DeepSeek match (title, judge reason) | Defensible? |
| --- | --- | --- |
| `hold_to_arm_late` b1 (DeepSeek) | Hold threshold is 600 ms, not 500 ms: Reported bug describes the same timing issue as the truth bug. | yes |
| `hold_to_arm_late` b1 (gpt-4o-mini) | Incorrect Armed LED Timing: Reported bug describes incorrect timing related to the armed LED, matching the true bug's timing issue. | yes (names the 600 ms vs 500 ms arm time) |
| `panel_dual_debounce_edge` b2 (DeepSeek) | No debounce/settle window: reported bug describes the same symptom of no debounce/settle window | yes in substance, with a crossed pairing (see below) |
| `cold_store_alarm` b1 (DeepSeek) | High-run not reset by mid-band samples: Reported bug describes the same root cause of consecutive high samples not being reset. | yes |

- `panel_dual_debounce_edge`: DeepSeek wrote two reports, "Toggles on release instead of press" and "No debounce/settle window". Both planted causes are named, but the judge paired them crossed (the release-edge report to b1, the debounce report to b2) and gave a wrong reason for b2. By report content b2 is found, so I count it as defensible. Both checks that expose b1 and b2 in the answer key are the same check (`a_tpp`).
- **Maximum gain: 3 bugs**, all three defensible. That is +2 on v2 (30/32 to 32/32) and +1 on the practice set (6/7 to 7/7); across 39 bugs 36 to 39. It is a ceiling: the same reading finds every one of them, but each also needs a check that fails honestly on the sketch and passes on the reference.

Reading matches that do not name the planted cause (my reading of the judge reasons and the report text):

- v2, DeepSeek, `blend_tank_sum_ovf` b1: the report is about a log line printed on a timer independent of the pct line, not about the int accumulator overflow. Judge reason says "integer overflow in ADC sample accumulation", which the report does not say. **Not defensible.**
- v2, DeepSeek, `cabin_heater_mul_ovf` b1: the report blames the 5000 mV reference and proposes the internal 1.1 V reference. The planted bug is `analogRead*5000` overflowing a 16-bit int. **Not defensible.**
- v2, gpt-4o-mini, `laundry_cycle_stuck` b1: report is "motor may not turn off within 600 ms", the planted bug is a RUN state that never exits. Same symptom area, cause not named. **Weak.**
- v2, gpt-4o-mini, `greenhouse_dual` b1 and b2: the report titles are right (fan state change frequency, missing range checks) but the judge reasons are crossed (b1's reason talks about out-of-range temperature, b2's about fan change limits). Match stands by title. **Defensible, judge text wrong.**
- Practice set (`bench/practice/README.md`): DeepSeek `door_chime_poll` (report is about a press during the chime, not a short press missed between samples) and gpt-4o-mini `orchard_spray_valve` (report is about debounce time; the judge's own reason mentions the millis() rollover). **Not defensible.**
- Counting these: DeepSeek 39 matches, 3 not defensible (36 defensible); gpt-4o-mini 31 matches, 2 not defensible plus 1 weak (29 defensible, 28 if the weak one is dropped). None of the five weak or not-defensible matches is in group 1, so they do not change the ceiling of 3. They do mean plain reading's recall is slightly lower than the table says.

### 5. Why Hexorcist missed each group 1 bug (from the stored runs)

**`hold_to_arm_late` b1** (arm delay 600 ms instead of 500 ms). Status `clean`, 0 bugs. *No check written for the arm delay, and the only related check was dropped by the cross-check.* The model wrote three checks: a1 (`output_follows` with `high_when D3==0`, `low_when D3==1`, within 100 ms), a2 serial period, a3 no_crash. Nothing demands "D8 HIGH within 550 ms of the press start". a1 asks for D8 HIGH within 100 ms of every press, which contradicts the 500 ms hold, so it fails in 10 scenarios on the sketch and in the same 10 on the reference (script: overlap 10 of 10; it ran as a1 `unconfirmed`, 10 of 10 shared with the clean rooms, so it was dropped as not a bug). Scenarios were adequate: `llm-1` holds 520 ms, `llm-2` 590 ms and `llm-6` 600 ms, which are exactly the window where the planted bug shows. `bench/results/dev_comparison.md` records that the first run found this bug only through a check that fails identically on the reference.

**`panel_dual_debounce_edge` b2** (acts on release edge instead of press). Hexorcist status `fixed`. *Found and reported, but credited to only b1 by the judge: a scoring miss, not a missing detection.* One check, a1 (`toggle_per_press`, "release does not toggle"), fails in 9 scenarios and produced one bug card titled "No debounce and wrong edge polarity cause multiple toggles per press"; its description says the toggle fires on release rather than press. The judge matched it to b1 and returned "No report matches the inverted pullup issue" for b2. The answer key ties both b1 and b2 to the same check (`a_tpp`), so one report on that check has to be matched against both bugs, and the judge credited it to one. The earlier README line "the second bug of `panel_dual_debounce_edge`" is the same case. In DeepSeek's reading the two causes were two separate reports, which the judge could match separately.

**`cold_store_alarm` b1** (high-sample count reset only at or below 8 °C, so spikes in the 8 to 12 °C band add up). Status `clean`, 0 bugs. *No check written for it; the one check that could fire was dropped by the cross-check.* The model merged spec bullets into a1 (raise at 12.0 °C, clear at 8.0 °C, edge mode) and wrote no equivalent of "isolated spikes never raise the alarm" (bullet 4, which is the frozen `a_spikes`). a1 fails in `builtin-spike-a1`, `llm-4` and `llm-5` because it demands the alarm for a single 30 ms spike, which the spec forbids; the two clean rooms fail it in the same 3 scenarios and the reference fails it in 4 (3 of them the same scenarios), so it was dropped as unconfirmed, correctly. Scenarios: `llm-9` alternates 615 mV (11.5 °C, mid-band) and 625 mV (12.5 °C) every 500 ms, which is the planted pattern, but with no check that says the alarm must stay off nothing can fail. `llm-4` and `llm-5` put spikes on a 550 mV base (5 °C), which is at or below the clear level, so they reset the count and would not expose the bug even with a check.  The run also dropped one invalid attack scenario (warning "Dropped an invalid attack scenario"; `llm-3` is missing from the list).

So the three misses fall into: no check written for the planted requirement (2: `hold_to_arm_late`, `cold_store_alarm`), and a report that exists but the scorer credited to one of two planted bugs on a shared check (1: `panel_dual_debounce_edge`). None of the three is a case where a scenario failed to trigger the bug and a check existed. A hypothesis pass that proposes the 500 ms arm requirement and the "mid-band spikes do not accumulate" requirement as checks would address the first two.

### Cross-checks run by script

- 39 bugs in the table: 32 v2 plus 7 practice. Judgement matches agree with the score files for all 39 on all three systems (0 mismatches).
- Groups: 1 = 3, 2 = 0, 3 = 0; hollow detections = 4; honest = 32.
