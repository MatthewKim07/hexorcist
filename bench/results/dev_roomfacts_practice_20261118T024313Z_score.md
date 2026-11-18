# Benchmark dev_roomfacts_practice_20261118T024313Z_score

Generated 2026-11-18T03:36:42.209655+00:00

## hexorcist

- Detection recall: 1.0 (2/2)
- False alarms: 3
- Compile rate: 80.00%
- Verified-fix rate: 60.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| silo_fill_gauge | accumulator_overflow | 1/1 | 0 | True | True | 145.13 | 0.00625198 |
| tank_mixer_cycle | narrow_timer | 1/1 | 1 | True | False | 145.09 | 0.00705018 |
| meadow_sprinkler_valve | correct | 0/0 | 1 | True | True | 120.95 | 0.00633476 |
| grain_bin_gauge | correct | 0/0 | 0 | False | False | 43.91 | 0.00213976 |
| loading_dock_horn | correct | 0/0 | 1 | True | True | 146.63 | 0.00607045 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.000848,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 4
}
```
