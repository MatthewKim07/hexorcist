# Adjudication of false alarms, run v2_full_20261115T003855Z

Strict scoring counts every report that the judge did not match to a frozen true bug as a false alarm. This document checks those reports against the specs. `bench/cases/` and the frozen ground truth are unchanged.

## Method

**Hexorcist.** All 27 strict false alarms were checked, plus every report on a correct case. Each report's own assertion and scenarios were replayed against the case's `reference.ino` (the known-good firmware; it is identical to `sketch.ino` on all 11 correct cases). If the known-good firmware fails the same check, the check or the evaluator is wrong, not the firmware. Each entry states how many of the report's failing scenarios also fail on the reference. Data: `bench/results/v2_full_20261115T003855Z_replay.json`.

Every cause is exactly one of:

- **A**: the sketch really violates a spec bullet that the frozen checks do not test. A valid finding.
- **B**: Hexorcist wrote an assertion that misreads the spec.
- **C**: Hexorcist's evaluator or harness judged wrongly.
- **D**: not a false alarm. The scorer's judge failed to mark a duplicate of a true bug. Outside A/B/C, listed so the counts add up.

**Baselines.** Baseline claims carry no measured evidence. Each of the 81 and 53 strict false alarms was read against the spec and the sketch. Only claims that were plausible violations or duplicates of a true bug are listed below, with a verdict. Every other claim contradicted the spec or the code, or named only a risk with no violated bullet. These verdicts come from reading and from measurements Hexorcist made on the same sketches, not from a run per claim, so the 'valid' counts are a lower bound.

**Scorer fix.** The judge sometimes returned a false-alarm index equal to the number of reports. `bench/score.py` now drops indices that name no report. Effect on strict counts: Hexorcist 31 to 27, DeepSeek baseline 83 to 81, gpt-4o-mini baseline unchanged (53). The as-scored files are in `bench/results/asscored/`.

## Counts for Hexorcist

| Cause | Reports on correct cases | False alarms on buggy cases | Total |
| --- | ---: | ---: | ---: |
| A sketch violates untested bullet | 1 | 1 | 2 |
| B assertion misreads spec | 11 | 11 | 22 |
| C evaluator or harness wrong | 1 | 0 | 1 |
| D duplicate of a true bug (not a false alarm) | 0 | 2 | 2 |
| **Total** | 13 | 14 | 27 |

Three correct cases (greenhouse_ok, lobby_lamp_ok, studio_siren_ok) produced no reports and no patch.

## Class C: bugs in Hexorcist's evaluator (most important)

**C1. An output pin used as a condition is read as constant 0.** `digital_input_levels()` in `backend/app/assertions.py` reads only pin events with `dir == 'in'`. When a model-written `output_follows` check uses an output pin as its condition (here LED D11 follows solenoid D8), the condition never changes, and the check demands the wrong level for the whole pulse. The firmware is correct in every case. It produced one false alarm and two reports that the scorer credited as duplicates of the true bug. All three kept their runs at `partial`.

- `solenoid_ok` a2 (false alarm): The check is correct, the evaluator is wrong. a2 uses the output pin D8 as its condition and digital_input_levels() only reads pin events with dir == 'in', so D8 is read as a constant 0. In llm-3 D11 goes LOW at 1024.1 ms, the same instant D8 goes HIGH, and returns HIGH at 3524.7 ms with D8. The evaluator demands D11 HIGH for the whole pulse. Run `9f582b806091`; evidence: "D11 was in the wrong state for 6573 ms across 3 interval(s), first at 825 ms: D11 was not HIGH for 2501 ms while required (grace 120 ms)." Reference also fails 16 of 16.
- `glue_solenoid_short` a2 (credited as duplicate, not counted): Same evaluator bug as solenoid_ok a2 (output pin D8 used as a condition is read as constant 0). Reference fails 15 of 15. Credited by the scorer as a duplicate of the pulse-length bug, so it is not in the false-alarm count, but it kept the run 'partial'. Run `d3aa64503d8a`; evidence: "D11 was in the wrong state for 8000 ms across 8 interval(s), first at 524 ms: D11 was not HIGH for 1000 ms while required (grace 50 ms)." Reference also fails 15 of 15.
- `mist_injector_long` a2 (credited as duplicate, not counted): Same evaluator bug (output pin D9 used as a condition). Reference fails 13 of 13. Credited as a duplicate of the pulse-length bug; kept the run 'partial'. Run `f31dab66facd`; evidence: "D12 was in the wrong state for 6000 ms across 3 interval(s), first at 825 ms: D12 was not HIGH for 2000 ms while required (grace 50 ms)." Reference also fails 13 of 13.

**C2. Input noise exceeds the ADC margin at threshold hovers (minor, cause inferred).** The evaluator takes the input once per 10 ms and allows a 10 mV ADC margin, but the built-in hover scenario adds 12 mV of noise. The likely cause is that a correct firmware reading a noisy sample inside the 10 ms window differs from the evaluator's view for 1 to 3 ms at the end of a required interval. Example: `lab_ph_ok` a4, builtin-hover-a1, 'D10 was not HIGH for 1 ms' at 794 ms (input 3236 mV last sample, threshold 3250 mV, D10 flips at 791 to 797 ms). The same 1 to 3 ms spans appear in `weather_ok` a5 and `weather_line_prefix` a5. Each of those reports is class B overall, because its other scenarios fail for larger reasons, so C2 adds no report to the C count.

## All Hexorcist false alarms and reports on correct cases

### Reports on correct cases (13)

**boiler_ok a1, class B.** Claim: "Valve reopens too slowly after lockout release" (output_follows, run `e20900224615`)
- Spec bullet: While D3 is held LOW, keep the valve CLOSED.
- Evidence: scenario "Lockout during firing": D6 was in the wrong state for 319 ms across 1 interval(s), first at 2.00 s: D6 was not HIGH for 319 ms while required (grace 500 ms). Reference also fails 2 of 2 failing scenarios.
- Why B: a1 demands the valve HIGH whenever temperature is below 70 °C and has no lockout exception. In llm-4, D6 is LOW from 2001 to 2321 ms, exactly while D3 is pressed (2000 to 2300 ms).

**boiler_ok a4, class B.** Claim: "Lockout key not debounced and polled only every 40 ms" (output_follows, run `e20900224615`)
- Spec bullet: Open the valve (HIGH) when temperature is below 70.0 °C; close the valve when temperature is above 75.0 °C.
- Evidence: scenario "Rapid oscillation (A1)": D6 was in the wrong state for 2520 ms across 25 interval(s), first at 560 ms: D6 was not HIGH for 121 ms while required (grace 500 ms). Reference also fails 10 of 10 failing scenarios.
- Why B: a4 demands the valve HIGH whenever D3 is released, whatever the temperature. The spec only says the lockout forces CLOSED; above 75 °C the valve must close, which a4 flags (ramp: 4159 ms).

**cooler_ok a4, class B.** Claim: "Compressor not driven ON promptly after service switch release" (output_follows, run `25b2c05df6cf`)
- Spec bullet: Turn the compressor ON when temperature reaches 8.0 °C or above, and OFF when temperature falls to 4.0 °C or below.
- Evidence: scenario "Button bounce (D4)": D7 was in the wrong state for 3871 ms across 5 interval(s), first at 500 ms: D7 was not HIGH for 500 ms while required (grace 500 ms). Reference also fails 13 of 13 failing scenarios.
- Why B: a4 demands the compressor HIGH whenever D4 is released, even below 4 °C where the spec requires OFF (hover 2021 ms, ramp 80 ms at 570 ms).

**laundry_ok a2, class B.** Claim: "Motor never starts when level begins at or above 25 cm" (output_follows, run `d24c0437561e`)
- Spec bullet: Enter FILL from IDLE when level is below 10.0 cm. (RUN follows FILL)
- Evidence: scenario "Nominal ramp (A0)": D10 was in the wrong state for 3550 ms across 1 interval(s), first at 2.53 s: D10 was not HIGH for 3550 ms while required (grace 600 ms). Reference also fails 3 of 3 failing scenarios.
- Why B: a2 demands the motor HIGH whenever level is at or above 25 cm. RUN is only reachable through FILL, which needs a start below 10 cm. The ramp scenario starts at 15 cm, so staying IDLE is correct (D10 LOW for 3550 ms).

**lock_ok a1, class B.** Claim: "Lock does not engage on a held request after door closes" (output_follows, run `c5f20ecb69f1`)
- Spec bullet: Do not re-engage while already locked; wait for a new request after unlock.
- Evidence: scenario "Button bounce (D2)": D9 was in the wrong state for 771 ms across 4 interval(s), first at 1.21 s: D9 was not HIGH for 192 ms while required (grace 200 ms). Reference also fails 5 of 5 failing scenarios.
- Why B: a1 demands D9 HIGH for as long as D2 is held LOW, with no door-closed condition and no 'new request' rule. Flagged intervals are a held button after the door opened (llm-8) and a door opening before debounce completes (llm-2, 2798 ms).

**loft_fan_ok a1, class B.** Claim: "Fan stays ON after boost release at low temperature" (output_follows, run `7cc75832a0e0`)
- Spec bullet: While D4 is held LOW, force the fan ON.
- Evidence: scenario "Out-of-range high then low with boost held": D5 was in the wrong state for 2833 ms across 1 interval(s), first at 3.32 s: D5 was not LOW for 2833 ms while required (grace 500 ms). Reference also fails 1 of 1 failing scenarios.
- Why B: a1 demands the fan OFF at 32 °C or below with no boost exception. In llm-10 D4 is held LOW at low temperature and D5 is correctly HIGH for 2833 ms.

**loft_fan_ok a2, class B.** Claim: "Boost override not applied while button held" (output_follows, run `7cc75832a0e0`)
- Spec bullet: Turn the fan ON at 36.0 °C or above; turn it OFF at 32.0 °C or below.
- Evidence: scenario "Floating A3 during hot state": D5 was in the wrong state for 8100 ms across 3 interval(s), first at 500 ms: D5 was not LOW for 3602 ms while required (grace 500 ms). Reference also fails 11 of 11 failing scenarios.
- Why B: a2 demands the fan OFF whenever D4 is released, whatever the temperature. In the ramp the fan is correctly ON at high temperature and a2 flags 4952 ms.

**loft_fan_ok a3, class A.** Claim: "Fan toggles far exceed 2 per 5000 ms window" (max_toggles, run `7cc75832a0e0`)
- Spec bullet: Fan must not change state more than 2 times in any 5000 ms window.
- Evidence: scenario "Short clean presses (D4)": D5 toggled 8 times in a 5000 ms window starting at 1.00 s (limit 2), and 8 times over the whole 8.00 s run. Reference also fails 4 of 4 failing scenarios.
- Why A: The sketch really breaks this bullet when the boost button is pressed: 8 changes in 5000 ms with short presses, 26 with rapid presses. The frozen scenarios never press D4. Boost forcing the fan ON conflicts with the limit, and the sketch picks boost.

**lab_ph_ok a3, class B.** Claim: "Range lamp chatters at the 8.50 threshold with no hysteresis" (output_follows, run `a17212b58703`)
- Spec bullet: Drive D10 HIGH when pH is outside 6.50–8.50 inclusive; otherwise LOW.
- Evidence: scenario "ADC quantisation near 6.50 boundary": D10 was in the wrong state for 3495 ms across 1330 interval(s), first at 500 ms: D10 was not LOW for 3 ms while required (grace 500 ms). Reference also fails 10 of 10 failing scenarios.
- Why B: The model split one band into two checks. a3 demands D10 LOW whenever pH is 8.5 or below, which includes everything under 6.5 where the spec requires HIGH.

**lab_ph_ok a4, class B.** Claim: "Range lamp chatters at the 6.50 threshold with no hysteresis" (output_follows, run `a17212b58703`)
- Spec bullet: Drive D10 HIGH when pH is outside 6.50–8.50 inclusive; otherwise LOW.
- Evidence: scenario "Noise burst around 8.50 upper threshold": D10 was in the wrong state for 2712 ms across 1067 interval(s), first at 500 ms: D10 was not LOW for 2 ms while required (grace 500 ms). Reference also fails 9 of 9 failing scenarios.
- Why B: a4 demands D10 LOW whenever pH is 6.5 or above, including above 8.5. With a3 it cannot be satisfied by any firmware. The 'chatter' evidence is 1 to 3 ms spans at the threshold plus whole-interval contradictions.

**solenoid_ok a2, class C.** Claim: "Armed LED stays LOW after solenoid pulse ends" (output_follows, run `9f582b806091`)
- Spec bullet: Keep D11 HIGH when idle and LOW while the solenoid pulse is active.
- Evidence: scenario "Rapid presses (D2)": D11 was in the wrong state for 6573 ms across 3 interval(s), first at 825 ms: D11 was not HIGH for 2501 ms while required (grace 120 ms). Reference also fails 16 of 16 failing scenarios.
- Why C: The check is correct, the evaluator is wrong. a2 uses the output pin D8 as its condition and digital_input_levels() only reads pin events with dir == 'in', so D8 is read as a constant 0. In llm-3 D11 goes LOW at 1024.1 ms, the same instant D8 goes HIGH, and returns HIGH at 3524.7 ms with D8. The evaluator demands D11 HIGH for the whole pulse.

**weather_ok a4, class B.** Claim: "Range lamp chatters at the 50 °C threshold (no hysteresis)" (output_follows, run `ecec34860d39`)
- Spec bullet: Light D7 when the reported temperature is outside -10.0 to 50.0 °C.
- Evidence: scenario "Lamp chatter at -10C boundary with noise": D7 was in the wrong state for 3332 ms across 1403 interval(s), first at 502 ms: D7 was not LOW for 2 ms while required (grace 500 ms). Reference also fails 14 of 14 failing scenarios.
- Why B: The model split one band into two checks. a4 demands D7 LOW at or below 50 °C, including below -10 °C. The narrative also touches a real defect (the freeze value is re-latched every loop) but the evidence comes from the invalid check.

**weather_ok a5, class B.** Claim: "Range lamp chatters at the -10 °C threshold (no hysteresis)" (output_follows, run `ecec34860d39`)
- Spec bullet: Light D7 when the reported temperature is outside -10.0 to 50.0 °C.
- Evidence: scenario "Lamp chatter at 50C boundary with noise": D7 was in the wrong state for 2660 ms across 1062 interval(s), first at 500 ms: D7 was not LOW for 2 ms while required (grace 500 ms). Reference also fails 8 of 8 failing scenarios.
- Why B: a5 demands D7 LOW at or above -10 °C, including above 50 °C. Contradicts a4 and the spec. Also uses the injected value, not the reported (frozen) value the spec names.

### False alarms on buggy cases (14)

**attic_vent_hyst a3, class D.** Claim: "Relay toggles far beyond 2 per 5000 ms due to no hysteresis or filtering" (max_toggles, run `8f2947726676`)
- Spec bullet: Fan must not change state more than 2 times in any 5000 ms window.
- Evidence: scenario "Threshold hover with noise (A0)": D8 toggled 57 times in a 5000 ms window starting at 900 ms (limit 2), and 77 times over the whole 8.00 s run. Reference also fails 3 of 13 failing scenarios.
- Why D: Not a false alarm. This is the frozen a_chatter check, the evidence of true bug b1 (missing hysteresis). The scorer's judge listed it as unmatched instead of a duplicate. In 10 of 13 failing scenarios the reference passes.

**blend_tank_sum_ovf a2, class A.** Claim: "Button handling blocks loop and stretches pct period" (serial_period, run `666baba905c1`)
- Spec bullet: Lines matching `pct: ` must appear every 1000 ms ±150 ms.
- Evidence: scenario "Button bounce (D5)": Expected /^pct: / every 1000 ± 150 ms; 4 of 7 intervals were out of tolerance, worst gap 1246 ms. Reference also fails 6 of 6 failing scenarios.
- Why A: With D5 held LOW the loop runs delay(30) per pass and the pct line comes every 1246 ms (994, 2241, 3486 ms). The known-good reference does the same (only the average type differs). The frozen scenario never presses D5.

**boiler_valve_failsafe a1, class B.** Claim: "Valve stays shut while cold after lockout release" (output_follows, run `2e3d09b2cab5`)
- Spec bullet: While D3 is held LOW, keep the valve CLOSED.
- Evidence: scenario "Lockout release while cold": D6 was in the wrong state for 2520 ms across 2 interval(s), first at 1.00 s: D6 was not HIGH for 2000 ms while required (grace 500 ms). Reference also fails 2 of 2 failing scenarios.
- Why B: Same defect as boiler_ok a1: no lockout exception. llm-2 and llm-7 hold D3 LOW while cold; D6 is correctly LOW.

**boiler_valve_failsafe a4, class B.** Claim: "Lockout key not debounced and valve not held closed while D3 LOW" (output_follows, run `2e3d09b2cab5`)
- Spec bullet: Open the valve (HIGH) when temperature is below 70.0 °C; close the valve when temperature is above 75.0 °C.
- Evidence: scenario "Rapid oscillation (A1)": D6 was in the wrong state for 2520 ms across 25 interval(s), first at 560 ms: D6 was not HIGH for 121 ms while required (grace 500 ms). Reference also fails 13 of 13 failing scenarios.
- Why B: Same defect as boiler_ok a4: demands HIGH whenever D3 is released, regardless of temperature. Reference fails 13 of 13 scenarios.

**cabin_heater_mul_ovf a2, class B.** Claim: "Frost override not honored within 600 ms on short/bouncy presses" (output_follows, run `129b82f39403`)
- Spec bullet: Turn the heater ON when temperature is below 18.0 °C and OFF when temperature is above 22.0 °C.
- Evidence: scenario "Button bounce (D2)": D9 was in the wrong state for 3371 ms across 5 interval(s), first at 600 ms: D9 was not LOW for 400 ms while required (grace 600 ms). Reference also fails 18 of 21 failing scenarios.
- Why B: a2 demands the heater OFF whenever D2 is released, whatever the temperature. The spec only forces ON while D2 is held LOW. Reference fails 18 of 21.

**cellar_pump_hyst a4, class B.** Claim: "Reported level is off by 0.2 cm because ADC scaling uses 5000 mV full scale" (serial_value_matches, run `cc04dcef7ab2`)
- Spec bullet: Every 800 ms print `sump cm=<level> pump=<0|1> mute=<0|1>` with level to one decimal place.
- Evidence: scenario "Button bounce (D4)": Firmware printed 29.8 cm at 832 ms while the injected input was 30.0 to 30.0 cm: off by 0.2 cm (tolerance ±0.1). 9 of 9 values were wrong. Reference also fails 8 of 8 failing scenarios.
- Why B: The spec gives a print format, not an accuracy bound. The model invented ±0.1 cm, finer than one ADC step (0.49 cm at 10 mV/cm). The reference prints 62.6 for 63.0 and fails 8 of 8.

**drip_scheduler_u8 a4, class B.** Claim: "D8 not held LOW while pause is asserted" (output_follows, run `88d6a4f45201`)
- Spec bullet: While D4 is held LOW, suppress new pulses and keep D8 LOW.
- Evidence: scenario "Rapid presses (D4)": D8 was in the wrong state for 721 ms across 15 interval(s), first at 902 ms: D8 was not HIGH for 48 ms while required (grace 100 ms). Reference also fails 11 of 11 failing scenarios.
- Why B: a4 has the same condition (D4 == 0) in both high_when and low_when, so it demands D8 HIGH and LOW at once. Reference fails 11 of 11.

**nav_beacon_byte_timer a3, class D.** Claim: "Beacon toggles too often due to slice-wrap double toggles" (max_toggles, run `3296268484e3`)
- Spec bullet: Beacon must not change state more than 5 times in any 2000 ms window during free blink.
- Evidence: scenario "quiet toggling every 2000 ms aligned with status": D12 toggled 8 times in a 2000 ms window starting at 245 ms (limit 5), and 24 times over the whole 10.00 s run. Reference also fails 0 of 14 failing scenarios.
- Why D: Not a false alarm. This is the frozen a_max check, the evidence of true bug b1 (8-bit timing). The scorer's judge listed it as unmatched instead of a duplicate. The reference passes it in 14 of 14.

**spindle_rpm_prefix a3, class B.** Claim: "D9 fails to light at over-speed due to mute handling and sampling" (output_follows, run `f8a2d871499a`)
- Spec bullet: Light D9 when rpm is at or above 2000 while mute is released.
- Evidence: scenario "Mute release mid-second lamp latency": D9 was in the wrong state for 2101 ms across 2 interval(s), first at 500 ms: D9 was not HIGH for 2002 ms while required (grace 500 ms). Reference also fails 3 of 3 failing scenarios.
- Why B: a3 ignores the mute input. In llm-3 and llm-5 D3 is held LOW and D9 is correctly OFF. Reference fails 3 of 3.

**spindle_rpm_prefix a4, class B.** Claim: "D9 chatters on noisy threshold readings" (output_follows, run `f8a2d871499a`)
- Spec bullet: While D3 is held LOW, keep D9 OFF regardless of rpm.
- Evidence: scenario "Threshold hover with noise (A5)": D9 was in the wrong state for 3353 ms across 37 interval(s), first at 900 ms: D9 was not LOW for 50 ms while required (grace 500 ms). Reference also fails 14 of 14 failing scenarios.
- Why B: The description is right but the condition is inverted: HIGH when D3 == 0, LOW when D3 == 1. It demands D9 LOW whenever mute is released, contradicting the over-speed lamp. Reference fails 14 of 14.

**walk_in_cooler_failsafe a4, class B.** Claim: "Service switch not honored and no hysteresis/debounce on D4" (output_follows, run `760b2ec1cb46`)
- Spec bullet: Turn the compressor ON when temperature reaches 8.0 °C or above, and OFF when temperature falls to 4.0 °C or below.
- Evidence: scenario "Button bounce (D4)": D7 was in the wrong state for 3871 ms across 5 interval(s), first at 500 ms: D7 was not HIGH for 500 ms while required (grace 500 ms). Reference also fails 11 of 11 failing scenarios.
- Why B: Same defect as cooler_ok a4: demands the compressor HIGH whenever D4 is released. Reference fails 11 of 11.

**weather_line_prefix a4, class B.** Claim: "Range lamp chatters at threshold with no hysteresis" (output_follows, run `1e50c308c3b6`)
- Spec bullet: Light D7 when the reported temperature is outside -10.0 to 50.0 °C.
- Evidence: scenario "threshold hover at -10C lower bound": D7 was in the wrong state for 3860 ms across 1571 interval(s), first at 501 ms: D7 was not LOW for 2 ms while required (grace 500 ms). Reference also fails 16 of 16 failing scenarios.
- Why B: Same defect as weather_ok a4 (one band split into two contradictory checks). Reference fails 16 of 16.

**weather_line_prefix a5, class B.** Claim: "Lamp follows live value during freeze and chatters at bounds" (output_follows, run `1e50c308c3b6`)
- Spec bullet: Light D7 when the reported temperature is outside -10.0 to 50.0 °C.
- Evidence: scenario "threshold hover at 50C with noise and lamp chatter": D7 was in the wrong state for 2941 ms across 1177 interval(s), first at 504 ms: D7 was not LOW for 1 ms while required (grace 500 ms). Reference also fails 7 of 7 failing scenarios.
- Why B: Same defect as weather_ok a5. Reference fails 7 of 7. The narrative names the freeze re-latch (a real defect) but the evidence comes from the invalid check.

**workshop_kpa_scale a3, class B.** Claim: "Gauge lamp driven from offset-corrupted pressure" (output_follows, run `8ee09c79837e`)
- Spec bullet: Drive D12 HIGH when pressure is at or above 90.0 kPa; otherwise LOW.
- Evidence: scenario "Glitch spike (A2)": D12 was in the wrong state for 1411 ms across 3 interval(s), first at 1.53 s: D12 was not LOW for 471 ms while required (grace 500 ms). Reference also fails 6 of 9 failing scenarios.
- Why B: The spec has no response time for the lamp. The model invented 500 ms; the firmware samples every 1000 ms (SAMPLE_MS), so the lamp lags up to 1 s. The reference fails 6 of 9 scenarios (lamp falls 210 to 750 ms late).

## Baseline false alarms examined

| System | Case | Claim | Spec bullet | Verdict | Reasoning |
| --- | --- | --- | --- | --- | --- |
| Baseline DeepSeek | weather_ok | Freeze updates frozen value instead of holding last sample | While D5 is held LOW, freeze the reported value at the last sample. | **valid finding** | The sketch sets frozenC = tempC on every loop while D5 is held, so the 'frozen' value tracks the live probe. The reference has the same code. Frozen checks never press D5. |
| Baseline DeepSeek | weather_line_prefix | Freeze captures live value instead of last sample | While D5 is held LOW, freeze the reported value at the last sample. | **valid finding** | Same freeze defect as weather_ok, present in this sketch as well. |
| Baseline DeepSeek | loft_fan_ok | No rate limit on fan toggles | Fan must not change state more than 2 times in any 5000 ms window. | **valid finding** | Boost presses change the fan state 8 times in 5000 ms (short presses) and 26 times (rapid presses); measured on the same sketch in Hexorcist's run. The frozen scenarios never press D4. |
| Baseline gpt-4o-mini | blend_tank_sum_ovf | Timing issue with sample button | Lines matching `pct: ` must appear every 1000 ms ±150 ms. | **valid finding** | The claim is that delay(30) while the sample button is held delays the pct line. Measured: 1246 ms gaps with D5 held (known-good reference too). gpt-4o-mini missed the overflow but found this. |
| Baseline DeepSeek | attic_vent_hyst | No rate limit on fan transitions | Fan must not change state more than 2 times in any 5000 ms window. | duplicate of true bug | The claim ties the rate violation to the missing hysteresis, the true bug b1. Not a false alarm; the judge did not dedupe it. |
| Baseline DeepSeek | cellar_pump_hyst | No toggle-rate limit | Pump output must not toggle more than 2 times in any 5000 ms window. | duplicate of true bug | Same root cause as the true bug b1 (single start threshold), reported via its symptom. |
| Baseline DeepSeek | greenhouse_dual | No rate limiting on fan state changes | Fan must not change state more than 2 times in any 5000 ms window. | duplicate of true bug | Same root cause as true bug b1 (missing hysteresis), reported via its symptom. |
| Baseline gpt-4o-mini | cellar_pump_hyst | Incorrect pump control logic | Start the pump at 45.0 cm or higher; stop it at 30.0 cm or lower. | duplicate of true bug | States that the pump stops below 45 cm instead of 30 cm, which is the true bug b1. |
| Baseline DeepSeek | greenhouse_ok | No rate limit on fan toggling | Fan must not change state more than 2 times in any 5000 ms window. | genuine false alarm | The sketch has a 4 °C hysteresis band; only an input that swings across the whole band can toggle it, which the spec demands. |
| Baseline DeepSeek | lock_ok | Re-engages while button held after unlock | Do not re-engage while already locked; wait for a new request after unlock. | genuine false alarm | Engagement only fires on a debounced edge (raw != stableReq), so a held button does not re-engage. The claim contradicts the code. |
| Baseline DeepSeek | cooler_ok | Floating sensor not detected as fault | If the sensor is floating ... force the compressor OFF within 500 ms. | genuine false alarm | Hexorcist's floating-sensor check passed on this sketch (D7 reached safe state LOW within 500 ms). |
| Baseline DeepSeek | boiler_ok | No debounce on lockout key | While D3 is held LOW, keep the valve CLOSED. | genuine false alarm | The spec has no debounce bullet and no run produced a bounce failure on this bullet; the claim is a plausible risk, not a shown violation. |
| Baseline DeepSeek | lab_ph_ok | pH offset missing — raw mV/500 gives 0–10 pH, not real pH | Convert ADC with a 5.000 V / 1023 span, then divide millivolts by 500 for pH. | genuine false alarm | The spec states the conversion the sketch implements. The claim contradicts the spec. |
| Baseline DeepSeek | drip_scheduler_u8 | Pulse not forced LOW immediately on pause | While D4 is held LOW, suppress new pulses and keep D8 LOW. | genuine false alarm | An in-flight 50 ms pulse finishes after a pause press. The reference does the same and the spec also says to complete each pulse. Reading is ambiguous, so not counted. |
| Baseline DeepSeek | blend_tank_sum_ovf | pct stream timing driven by sample count, not 1000 ms | Lines matching `pct: ` must appear every 1000 ms ±150 ms. | genuine false alarm | The mechanism given (period driven by sample count) is not the cause; the pct gap is within tolerance without a button press. The real cause (delay(30) with D5 held) is not named here. |
| Baseline DeepSeek | blend_tank_sum_ovf | Force button emits note every loop while held | Holding D5 LOW may emit a `blend force last=<n>` note without replacing the periodic `pct:` stream. | genuine false alarm | The headline is that the force note floods serial, which the spec allows. The pct delay is mentioned only in passing. |
| Baseline DeepSeek | kiln_door_block | No debounce/hysteresis on door switch | A settled door-open press as short as 40 ms starts a 2000 ms HIGH pulse on D8 within 150 ms. | genuine false alarm | The sketch has no debounce, but under bounce it still produced exactly 2000 ms pulses in Hexorcist's check, so no violation was shown. |
| Baseline DeepSeek | porch_gate_block | Chime retriggers while already sounding | Presses while the chime is already sounding are ignored (pulse length is not restarted). | **valid finding** | Measured in the builtin-bounce-d3 scenario: D3 is pressed at 2500 ms while the chime runs (1000 to 2800 ms). The sketch restarts the chime at 2800 ms, giving one 3600 ms pulse. The reference ignores that press and pulses 1000 to 2800 ms only. The frozen a_pulse check passes because the engine allows a trigger held past a pulse's end to fire again. |
| Baseline DeepSeek | spindle_rpm_prefix | RPM scaling wrong by ~10x | Tach input on A5 at 1 mV per rpm. | genuine false alarm | The reference prints values within ±50 rpm, so the scaling is correct. The claim is wrong. |
| Baseline DeepSeek | hoist_estop_invert | Contactor never follows run request | When e-stop is clear, keep the contactor available (HIGH) for hoist motion. | genuine false alarm | The spec asks for HIGH whenever e-stop is clear; run request D6 is not a condition. The reference behaves the same. |
| Baseline gpt-4o-mini | loft_fan_ok | Incorrect fan state change frequency | Fan must not change state more than 2 times in any 5000 ms window. | genuine false alarm | The outcome claim is true under boost presses, but the stated mechanism (hold counters reset every sample) is wrong; no evidence of the real trigger. |
| Baseline gpt-4o-mini | weather_ok | Range lamp logic error | Light D7 when the reported temperature is outside -10.0 to 50.0 °C. | genuine false alarm | The lamp is driven LOW in range and HIGH out of range, as the spec says. The claim is wrong. |
| Baseline gpt-4o-mini | lab_ph_ok | Incorrect LED Logic | Drive D10 HIGH when pH is outside 6.50–8.50 inclusive; otherwise LOW. | genuine false alarm | The sketch drives D10 HIGH out of band, as specified. The claim reads the logic backwards. |

| System | Strict false alarms | Valid findings | Duplicates of true bugs | Adjudicated false alarms |
| --- | ---: | ---: | ---: | ---: |
| Baseline DeepSeek | 81 | 4 | 3 | 74 |
| Baseline gpt-4o-mini | 53 | 1 | 1 | 51 |
| Hexorcist (DeepSeek) | 27 | 2 | 2 | 23 |
