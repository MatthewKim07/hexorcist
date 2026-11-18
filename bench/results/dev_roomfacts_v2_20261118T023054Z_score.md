# Benchmark dev_roomfacts_v2_20261118T023054Z_score

Generated 2026-11-18T03:36:03.620728+00:00

## hexorcist

- Detection recall: 1.0 (3/3)
- False alarms: 1
- Compile rate: 66.67%
- Verified-fix rate: 33.33%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| glue_solenoid_short | timed_pulse_length | 1/1 | 0 | True | True | 83.02 | 0.00491177 |
| nav_beacon_byte_timer | millis_rollover | 1/1 | 0 | True | False | 158.47 | 0.00629098 |
| rail_limit_invert | inverted_pullup | 1/1 | 0 | True | True | 95.1 | 0.004665 |
| weather_ok | correct | 0/0 | 0 | False | False | 51.39 | 0.00233604 |
| loft_fan_ok | correct | 0/0 | 1 | True | False | 283.86 | 0.00818815 |
| lab_ph_ok | correct | 0/0 | 0 | False | False | 45.44 | 0.00201054 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.000736,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.05,
  "cap_strong": 2.0,
  "calls": 4
}
```
