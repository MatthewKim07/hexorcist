# Benchmark practice_baseline_deepseek_20261117_score

Generated 2026-11-17T21:53:58.275674+00:00

## baseline

- Detection recall: 1.0 (7/7)
- False alarms: 13
- Compile rate: 100.00%
- Verified-fix rate: 70.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| cold_store_alarm | noise_filter | 1/1 | 0 | True | True | 3.57 | 0.00060578 |
| door_chime_poll | press_vs_sample_period | 1/1 | 2 | True | False | 4.27 | 0.00064652 |
| grain_bin_gauge | correct | 0/0 | 3 | True | False | 5.35 | 0.00067886 |
| lift_call_panel | blocking_wait | 1/1 | 0 | True | True | 4.2 | 0.000595 |
| loading_dock_horn | correct | 0/0 | 2 | True | True | 3.27 | 0.00054558 |
| meadow_sprinkler_valve | correct | 0/0 | 2 | True | True | 4.56 | 0.0006083 |
| orchard_spray_valve | millis_rollover | 1/1 | 1 | True | True | 3.33 | 0.00060928 |
| silo_fill_gauge | accumulator_overflow | 1/1 | 0 | True | True | 6.75 | 0.00077994 |
| stair_light_timer | feature_interaction | 1/1 | 1 | True | True | 3.99 | 0.00068796 |
| tank_mixer_cycle | narrow_timer | 1/1 | 2 | True | False | 4.7 | 0.0006678 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.001969,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 10
}
```
