# Benchmark dev_practice2_20261118T063831Z_score

Generated 2026-11-18T07:19:36.820064+00:00

## hexorcist

- Detection recall: 0.8571428571428571 (6/7)
- False alarms: 3
- Compile rate: 70.00%
- Verified-fix rate: 50.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| cold_store_alarm | noise_filter | 0/1 | 0 | False | False | 104.38 | 0.00572615 |
| door_chime_poll | press_vs_sample_period | 1/1 | 0 | True | True | 117.92 | 0.00449833 |
| grain_bin_gauge | correct | 0/0 | 0 | False | False | 48.42 | 0.00221788 |
| lift_call_panel | blocking_wait | 1/1 | 1 | True | True | 140.56 | 0.00740846 |
| loading_dock_horn | correct | 0/0 | 0 | False | False | 39.4 | 0.00211428 |
| meadow_sprinkler_valve | correct | 0/0 | 1 | True | True | 111.9 | 0.00460388 |
| orchard_spray_valve | millis_rollover | 1/1 | 0 | True | False | 120.97 | 0.00638023 |
| silo_fill_gauge | accumulator_overflow | 1/1 | 0 | True | True | 143.57 | 0.00547448 |
| stair_light_timer | feature_interaction | 1/1 | 0 | True | True | 60.45 | 0.00465459 |
| tank_mixer_cycle | narrow_timer | 1/1 | 1 | True | False | 137.5 | 0.0090682 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.001405,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 7
}
```
