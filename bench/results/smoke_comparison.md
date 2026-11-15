# Smoke test (5 DEV cases): run dev_smoke_20261115T084912Z against v2_full_20261115T003855Z

DEV-set numbers on cases chosen because they had false alarms or partial runs. Five cases, one run each: indicative only.

| Case | Status old → new | Strict false alarms old → new | Unconfirmed (new) | Found by search | Frozen checks on the patch old → new | Cost old → new | Time s old → new |
| --- | --- | --- | --- | --- | --- | --- | --- |
| solenoid_ok | partial → clean | 1 → 0 | 1 | 0 | pass → no patch | $0.0066 → $0.0025 | 79 → 77 |
| loft_fan_ok | partial → partial | 3 → 1 | 1 | 0 | pass → pass | $0.0078 → $0.0067 | 193 → 278 |
| lab_ph_ok | partial → clean | 2 → 0 | 2 | 0 | pass → no patch | $0.0074 → $0.0028 | 157 → 134 |
| cellar_pump_hyst | partial → fixed | 1 → 0 | 1 | 0 | pass → pass | $0.0081 → $0.0043 | 192 → 183 |
| nav_beacon_byte_timer | partial → partial | 1 → 0 | 2 | 0 | fail → fail (a_max, a_period) | $0.0089 → $0.0057 | 116 → 163 |
| Total | | 8 → 1 | 7 | 0 | | $0.0387 → $0.0219 | 737 → 835 |

Recall: 2/2 true bugs in both runs. Spec grounding dropped 0 of 16 assertions. Search ran 150 variants, 0 new failing checks.

Known flaw found here: nav_beacon a2 (serial_period, the real tick-period bug) was marked unconfirmed because the clean-room sketch never printed the line ("no line matched") and the uploaded one printed it at the wrong period. Fixed in b095256 (silent and wrong text failures no longer count as the same way). Not re-run.
