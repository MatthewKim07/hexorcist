# Benchmark v2_full_20261115T003855Z_score_openai

Generated 2026-11-15T04:35:14.797238+00:00

## baseline

- Detection recall: 0.875 (28/32)
- False alarms: 53
- Compile rate: 100.00%
- Verified-fix rate: 60.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| aquarium_ph_scale | wrong_unit_scaling | 1/1 | 1 | True | True | 11.93 | 0.00053925 |
| attic_vent_hyst | missing_hysteresis | 1/1 | 1 | True | False | 11.96 | 0.0006702 |
| bench_led_miswire | wrong_pin | 1/1 | 1 | True | True | 0.0 | 0.0005373 |
| blend_tank_sum_ovf | integer_overflow | 0/1 | 2 | True | False | 10.68 | 0.00053595 |
| boiler_ok | correct | 0/0 | 2 | True | True | 11.44 | 0.00063075 |
| boiler_valve_failsafe | missing_failsafe | 1/1 | 2 | True | False | 12.59 | 0.00064395 |
| cabin_heater_mul_ovf | integer_overflow | 1/1 | 1 | True | False | 10.03 | 0.00056865 |
| cellar_pump_hyst | missing_hysteresis | 1/1 | 2 | True | False | 14.46 | 0.000708 |
| cooler_ok | correct | 0/0 | 2 | True | True | 13.29 | 0.00069555 |
| drip_scheduler_u8 | millis_rollover | 1/1 | 1 | True | True | 12.18 | 0.0005538 |
| foyer_lamp_debounce | missing_debounce | 1/1 | 0 | True | False | 8.13 | 0.0004908 |
| glue_solenoid_short | timed_pulse_length | 1/1 | 0 | True | True | 10.91 | 0.0005919 |
| greenhouse_dual | missing_hysteresis,missing_failsafe | 2/2 | 0 | True | False | 0.0 | 0.00068025 |
| greenhouse_ok | correct | 0/0 | 3 | True | True | 15.98 | 0.00089745 |
| hoist_estop_invert | inverted_pullup | 1/1 | 1 | True | False | 9.78 | 0.0005946 |
| hold_to_arm_late | off_by_one_timing | 1/1 | 1 | True | True | 9.76 | 0.0005523 |
| inject_pulse_short | off_by_one_timing | 1/1 | 1 | True | True | 9.9 | 0.00056205 |
| kiln_door_block | blocking_delay | 1/1 | 1 | True | True | 7.45 | 0.0004695 |
| lab_ph_ok | correct | 0/0 | 2 | True | True | 9.23 | 0.0005388 |
| laundry_cycle_stuck | stuck_state_machine | 1/1 | 1 | True | True | 10.8 | 0.00071475 |
| laundry_ok | correct | 0/0 | 2 | True | True | 13.19 | 0.0007278 |
| lobby_lamp_ok | correct | 0/0 | 2 | True | True | 9.04 | 0.00050595 |
| lock_ok | correct | 0/0 | 2 | True | True | 12.59 | 0.0006501 |
| loft_fan_ok | correct | 0/0 | 2 | True | False | 0.0 | 0.00068295 |
| mist_injector_long | timed_pulse_length | 1/1 | 1 | True | True | 10.56 | 0.000573 |
| nav_beacon_byte_timer | millis_rollover | 1/1 | 2 | True | False | 10.22 | 0.0006009 |
| panel_dual_debounce_edge | missing_debounce,inverted_pullup | 1/2 | 1 | True | False | 9.24 | 0.00048435 |
| porch_gate_block | blocking_delay | 1/1 | 1 | True | False | 6.82 | 0.0004587 |
| process_dual_block_scale | wrong_unit_scaling,blocking_delay | 2/2 | 0 | True | True | 9.23 | 0.0005385 |
| rail_limit_invert | inverted_pullup | 1/1 | 0 | True | False | 12.14 | 0.00058815 |
| shop_estop_debounce | missing_debounce | 1/1 | 1 | True | True | 8.44 | 0.00049335 |
| solenoid_ok | correct | 0/0 | 2 | True | True | 12.45 | 0.00058965 |
| spindle_rpm_prefix | serial_format | 1/1 | 1 | True | False | 10.1 | 0.00058455 |
| studio_siren_ok | correct | 0/0 | 2 | True | True | 9.99 | 0.0005463 |
| vault_lock_stuck | stuck_state_machine | 0/1 | 2 | True | False | 10.93 | 0.0006381 |
| walk_in_cooler_failsafe | missing_failsafe | 1/1 | 0 | True | True | 11.45 | 0.00068715 |
| weather_line_prefix | serial_format | 0/1 | 2 | True | False | 11.27 | 0.00055365 |
| weather_ok | correct | 0/0 | 2 | True | True | 9.18 | 0.00054525 |
| workshop_kpa_scale | wrong_unit_scaling | 1/1 | 1 | True | True | 10.34 | 0.00056115 |
| yard_relay_miswire | wrong_pin | 1/1 | 2 | True | True | 11.3 | 0.00059355 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.006981,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 3.0,
  "calls": 38
}
```
