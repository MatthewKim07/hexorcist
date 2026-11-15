# Benchmark v2_full_20261115T003855Z_score_deepseek

Generated 2026-11-15T04:30:21.963447+00:00

## baseline

- Detection recall: 1.0 (32/32)
- False alarms: 83
- Compile rate: 100.00%
- Verified-fix rate: 95.00%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| aquarium_ph_scale | wrong_unit_scaling | 1/1 | 0 | True | True | 3.01 | 0.00053116 |
| attic_vent_hyst | missing_hysteresis | 1/1 | 3 | True | True | 5.09 | 0.00080794 |
| bench_led_miswire | wrong_pin | 1/1 | 3 | True | True | 4.08 | 0.00062846 |
| blend_tank_sum_ovf | integer_overflow | 1/1 | 6 | True | True | 5.36 | 0.0007203 |
| boiler_ok | correct | 0/0 | 4 | True | True | 5.78 | 0.00081886 |
| boiler_valve_failsafe | missing_failsafe | 1/1 | 1 | True | True | 3.79 | 0.00066122 |
| cabin_heater_mul_ovf | integer_overflow | 1/1 | 1 | True | True | 3.92 | 0.00064162 |
| cellar_pump_hyst | missing_hysteresis | 1/1 | 4 | True | True | 5.44 | 0.0008603 |
| cooler_ok | correct | 0/0 | 4 | True | True | 7.06 | 0.00093198 |
| drip_scheduler_u8 | millis_rollover | 1/1 | 2 | True | True | 4.29 | 0.00066962 |
| foyer_lamp_debounce | missing_debounce | 1/1 | 0 | True | True | 3.4 | 0.00053452 |
| glue_solenoid_short | timed_pulse_length | 1/1 | 2 | True | True | 4.49 | 0.00066962 |
| greenhouse_dual | missing_hysteresis,missing_failsafe | 2/2 | 3 | True | True | 6.48 | 0.00088004 |
| greenhouse_ok | correct | 0/0 | 1 | True | True | 7.19 | 0.001036 |
| hoist_estop_invert | inverted_pullup | 1/1 | 1 | True | False | 4.05 | 0.00065268 |
| hold_to_arm_late | off_by_one_timing | 1/1 | 2 | True | True | 3.25 | 0.00059794 |
| inject_pulse_short | off_by_one_timing | 1/1 | 1 | True | True | 3.25 | 0.00056322 |
| kiln_door_block | blocking_delay | 1/1 | 3 | True | True | 5.15 | 0.0006405 |
| lab_ph_ok | correct | 0/0 | 2 | True | True | 3.99 | 0.0006097 |
| laundry_cycle_stuck | stuck_state_machine | 1/1 | 1 | True | True | 3.66 | 0.00071148 |
| laundry_ok | correct | 0/0 | 3 | True | True | 5.01 | 0.00079422 |
| lobby_lamp_ok | correct | 0/0 | 2 | True | True | 4.06 | 0.00055832 |
| lock_ok | correct | 0/0 | 3 | True | True | 5.2 | 0.00069958 |
| loft_fan_ok | correct | 0/0 | 4 | True | True | 5.36 | 0.0007945 |
| mist_injector_long | timed_pulse_length | 1/1 | 1 | True | True | 3.5 | 0.00061376 |
| nav_beacon_byte_timer | millis_rollover | 1/1 | 2 | True | True | 4.32 | 0.00064722 |
| panel_dual_debounce_edge | missing_debounce,inverted_pullup | 2/2 | 1 | True | True | 3.5 | 0.00054278 |
| porch_gate_block | blocking_delay | 1/1 | 3 | True | True | 4.37 | 0.00064694 |
| process_dual_block_scale | wrong_unit_scaling,blocking_delay | 2/2 | 1 | True | True | 3.9 | 0.00056826 |
| rail_limit_invert | inverted_pullup | 1/1 | 2 | True | False | 3.69 | 0.00064526 |
| shop_estop_debounce | missing_debounce | 1/1 | 2 | True | True | 3.17 | 0.00053634 |
| solenoid_ok | correct | 0/0 | 3 | True | True | 4.48 | 0.00065856 |
| spindle_rpm_prefix | serial_format | 1/1 | 2 | True | True | 4.3 | 0.00068222 |
| studio_siren_ok | correct | 0/0 | 2 | True | True | 3.93 | 0.000581 |
| vault_lock_stuck | stuck_state_machine | 1/1 | 1 | True | True | 3.15 | 0.0005733 |
| walk_in_cooler_failsafe | missing_failsafe | 1/1 | 1 | True | True | 5.5 | 0.00080626 |
| weather_line_prefix | serial_format | 1/1 | 3 | True | True | 3.93 | 0.00066766 |
| weather_ok | correct | 0/0 | 3 | True | True | 3.89 | 0.00065534 |
| workshop_kpa_scale | wrong_unit_scaling | 1/1 | 0 | True | True | 3.28 | 0.00058436 |
| yard_relay_miswire | wrong_pin | 1/1 | 0 | True | True | 2.52 | 0.00053788 |

## hexorcist

- Detection recall: 0.96875 (31/32)
- False alarms: 31
- Compile rate: 92.50%
- Verified-fix rate: 87.50%

| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| aquarium_ph_scale | wrong_unit_scaling | 1/1 | 0 | True | True | 113.4 | 0.00494718 |
| attic_vent_hyst | missing_hysteresis | 1/1 | 1 | True | True | 140.47 | 0.00989716 |
| bench_led_miswire | wrong_pin | 1/1 | 0 | True | True | 78.65 | 0.0075474 |
| blend_tank_sum_ovf | integer_overflow | 1/1 | 1 | True | True | 140.42 | 0.00497826 |
| boiler_ok | correct | 0/0 | 2 | True | True | 107.32 | 0.00832972 |
| boiler_valve_failsafe | missing_failsafe | 1/1 | 3 | True | True | 137.55 | 0.0089474 |
| cabin_heater_mul_ovf | integer_overflow | 1/1 | 1 | True | False | 131.36 | 0.0080038 |
| cellar_pump_hyst | missing_hysteresis | 1/1 | 2 | True | True | 191.74 | 0.0080766 |
| cooler_ok | correct | 0/0 | 1 | True | True | 197.85 | 0.00817726 |
| drip_scheduler_u8 | millis_rollover | 1/1 | 1 | True | True | 102.71 | 0.00887894 |
| foyer_lamp_debounce | missing_debounce | 1/1 | 0 | True | True | 60.4 | 0.00332948 |
| glue_solenoid_short | timed_pulse_length | 1/1 | 0 | True | True | 62.01 | 0.0083685 |
| greenhouse_dual | missing_hysteresis,missing_failsafe | 2/2 | 0 | True | True | 126.81 | 0.00519078 |
| greenhouse_ok | correct | 0/0 | 0 | False | False | 49.87 | 0.0029834 |
| hoist_estop_invert | inverted_pullup | 1/1 | 0 | True | True | 58.93 | 0.00379946 |
| hold_to_arm_late | off_by_one_timing | 1/1 | 0 | True | True | 113.28 | 0.00551866 |
| inject_pulse_short | off_by_one_timing | 1/1 | 0 | True | True | 49.86 | 0.00336826 |
| kiln_door_block | blocking_delay | 1/1 | 0 | True | True | 55.92 | 0.00349496 |
| lab_ph_ok | correct | 0/0 | 2 | True | True | 157.16 | 0.00738752 |
| laundry_cycle_stuck | stuck_state_machine | 1/1 | 0 | True | True | 102.68 | 0.00407806 |
| laundry_ok | correct | 0/0 | 1 | True | True | 98.2 | 0.0043064 |
| lobby_lamp_ok | correct | 0/0 | 0 | False | False | 30.26 | 0.00172578 |
| lock_ok | correct | 0/0 | 1 | True | True | 83.11 | 0.00661458 |
| loft_fan_ok | correct | 0/0 | 3 | True | True | 193.21 | 0.00776524 |
| mist_injector_long | timed_pulse_length | 1/1 | 0 | True | True | 119.35 | 0.00835072 |
| nav_beacon_byte_timer | millis_rollover | 1/1 | 1 | True | False | 116.37 | 0.00886536 |
| panel_dual_debounce_edge | missing_debounce,inverted_pullup | 1/2 | 0 | True | True | 51.43 | 0.00310772 |
| porch_gate_block | blocking_delay | 1/1 | 0 | True | True | 52.92 | 0.0035245 |
| process_dual_block_scale | wrong_unit_scaling,blocking_delay | 2/2 | 0 | True | True | 80.1 | 0.00491512 |
| rail_limit_invert | inverted_pullup | 1/1 | 0 | True | True | 60.48 | 0.0034797 |
| shop_estop_debounce | missing_debounce | 1/1 | 0 | True | True | 68.0 | 0.00317114 |
| solenoid_ok | correct | 0/0 | 1 | True | True | 78.55 | 0.00663222 |
| spindle_rpm_prefix | serial_format | 1/1 | 3 | True | True | 122.3 | 0.00761306 |
| studio_siren_ok | correct | 0/0 | 0 | False | False | 40.84 | 0.0017542 |
| vault_lock_stuck | stuck_state_machine | 1/1 | 0 | True | True | 90.63 | 0.00543368 |
| walk_in_cooler_failsafe | missing_failsafe | 1/1 | 1 | True | True | 163.19 | 0.00844998 |
| weather_line_prefix | serial_format | 1/1 | 3 | True | True | 164.52 | 0.01012452 |
| weather_ok | correct | 0/0 | 2 | True | True | 197.74 | 0.00744856 |
| workshop_kpa_scale | wrong_unit_scaling | 1/1 | 1 | True | True | 87.58 | 0.00413826 |
| yard_relay_miswire | wrong_pin | 1/1 | 0 | True | True | 93.65 | 0.00810502 |

## Budget
```
{
  "spent_deepseek": 0.0,
  "spent_openai": 0.016221,
  "spent_other": 0.0,
  "cap_deepseek": 0.8,
  "cap_openai": 3.0,
  "calls": 77
}
```
