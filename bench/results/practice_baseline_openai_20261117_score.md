# Benchmark practice_baseline_openai_20261117_score

Generated 2026-11-17T21:55:36.899595+00:00

## baseline

- Detection recall: 0.42857142857142855 (3/7)
- False alarms: 16
- Compile rate: 100.00%
- Verified-fix rate: 20.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| cold_store_alarm | noise_filter | 0/1 | 2 | True | False | 13.21 | 0.00061155 |
| door_chime_poll | press_vs_sample_period | 0/1 | 2 | True | False | 13.05 | 0.00054375 |
| grain_bin_gauge | correct | 0/0 | 2 | True | False | 9.47 | 0.0005142 |
| lift_call_panel | blocking_wait | 1/1 | 1 | True | False | 9.7 | 0.0004941 |
| loading_dock_horn | correct | 0/0 | 2 | True | True | 10.11 | 0.0005007 |
| meadow_sprinkler_valve | correct | 0/0 | 2 | True | True | 9.81 | 0.00054075 |
| orchard_spray_valve | millis_rollover | 1/1 | 1 | True | False | 10.0 | 0.0005628 |
| silo_fill_gauge | accumulator_overflow | 1/1 | 1 | True | False | 9.76 | 0.00052215 |
| stair_light_timer | feature_interaction | 0/1 | 2 | True | False | 11.4 | 0.0006312 |
| tank_mixer_cycle | narrow_timer | 0/1 | 1 | True | False | 9.0 | 0.0004536 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.001768,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 10
}
```
