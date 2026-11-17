# Benchmark dev_gate_smoke_20261117T002104Z_score

Generated 2026-11-17T00:48:47.749498+00:00

## hexorcist

- Detection recall: 0.8888888888888888 (8/9)
- False alarms: 3
- Compile rate: 80.00%
- Verified-fix rate: 80.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| weather_ok | correct | 0/0 | 0 | False | False | 57.41 | 0.00218694 |
| weather_line_prefix | serial_format | 1/1 | 0 | True | True | 178.19 | 0.00446109 |
| lab_ph_ok | correct | 0/0 | 0 | False | False | 43.85 | 0.00206724 |
| loft_fan_ok | correct | 0/0 | 2 | True | True | 297.14 | 0.00916928 |
| attic_vent_hyst | missing_hysteresis | 1/1 | 0 | True | True | 122.27 | 0.00495539 |
| cellar_pump_hyst | missing_hysteresis | 1/1 | 1 | True | True | 227.83 | 0.00914912 |
| foyer_lamp_debounce | missing_debounce | 1/1 | 0 | True | True | 102.62 | 0.00374657 |
| greenhouse_dual | missing_hysteresis,missing_failsafe | 2/2 | 0 | True | True | 162.98 | 0.0053839 |
| panel_dual_debounce_edge | missing_debounce,inverted_pullup | 1/2 | 0 | True | True | 75.47 | 0.00382748 |
| shop_estop_debounce | missing_debounce | 1/1 | 0 | True | True | 111.69 | 0.00399045 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.001746,
  "spent_strong": 0.0,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 0.3,
  "cap_strong": 2.0,
  "calls": 8
}
```
