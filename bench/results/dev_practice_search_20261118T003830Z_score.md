# Benchmark dev_practice_search_20261118T003830Z_score

Generated 2026-11-18T01:04:08.115799+00:00

## hexorcist

- Detection recall: 0.7142857142857143 (5/7)
- False alarms: 2
- Compile rate: 60.00%
- Verified-fix rate: 50.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| cold_store_alarm | noise_filter | 1/1 | 0 | True | True | 178.3 | 0.00906579 |
| door_chime_poll | press_vs_sample_period | 0/1 | 0 | False | False | 87.7 | 0.00217476 |
| grain_bin_gauge | correct | 0/0 | 0 | False | False | 95.23 | 0.00212842 |
| lift_call_panel | blocking_wait | 1/1 | 1 | True | True | 157.11 | 0.0063298 |
| loading_dock_horn | correct | 0/0 | 0 | False | False | 77.15 | 0.00211176 |
| meadow_sprinkler_valve | correct | 0/0 | 1 | True | True | 164.67 | 0.00411326 |
| orchard_spray_valve | millis_rollover | 1/1 | 0 | True | False | 113.17 | 0.00419809 |
| silo_fill_gauge | accumulator_overflow | 0/1 | 0 | False | False | 171.98 | 0.00482074 |
| stair_light_timer | feature_interaction | 1/1 | 0 | True | True | 73.94 | 0.00428503 |
| tank_mixer_cycle | narrow_timer | 1/1 | 0 | True | True | 212.9 | 0.00738884 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.001368,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 7
}
```
