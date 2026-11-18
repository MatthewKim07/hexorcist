# Benchmark dev_practice_20261118T002318Z_score

Generated 2026-11-18T01:03:14.796454+00:00

## hexorcist

- Detection recall: 0.7142857142857143 (5/7)
- False alarms: 2
- Compile rate: 60.00%
- Verified-fix rate: 50.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| cold_store_alarm | noise_filter | 0/1 | 0 | False | False | 105.57 | 0.00343715 |
| door_chime_poll | press_vs_sample_period | 1/1 | 0 | True | True | 107.14 | 0.00403303 |
| grain_bin_gauge | correct | 0/0 | 0 | False | False | 48.33 | 0.00224462 |
| lift_call_panel | blocking_wait | 1/1 | 1 | True | True | 141.99 | 0.00498954 |
| loading_dock_horn | correct | 0/0 | 0 | False | False | 37.81 | 0.00203196 |
| meadow_sprinkler_valve | correct | 0/0 | 1 | True | True | 96.74 | 0.00399842 |
| orchard_spray_valve | millis_rollover | 1/1 | 0 | True | True | 86.15 | 0.00412967 |
| silo_fill_gauge | accumulator_overflow | 0/1 | 0 | False | False | 98.23 | 0.00322216 |
| stair_light_timer | feature_interaction | 1/1 | 0 | True | True | 60.47 | 0.00441683 |
| tank_mixer_cycle | narrow_timer | 1/1 | 0 | True | False | 98.27 | 0.00400754 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.001422,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 8
}
```
