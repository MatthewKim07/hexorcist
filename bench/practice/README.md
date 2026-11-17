# Practice set: hidden-behaviour cases

Ten small firmware cases in the same format as `bench/cases/` (`spec.md`, `pins.json`, `sketch.ino`, `reference.ino`, `truth.json`, `checks.json`). Seven have one planted bug and three are correct decoys that look suspicious but meet their spec. The bugs are the kind that reading the code rarely settles: they show up only when the firmware runs under the right conditions (a clock near a rollover, an input at a certain moment, a high reading).

**This set is for tuning.** It is not frozen. Unlike `bench/cases/` (the v2 DEV set, frozen by hash) and the held-out v3 set (not written), cases here may be changed, replaced or added while the agent is developed against them. Results on this set show whether a change reaches a hidden behaviour. They say nothing about unseen firmware, and they must never be reported as a held-out score. The fingerprint below only says which version of the set a result belongs to.

## Cases

| Case | Kind | What the planted bug is, and what exposes it |
| --- | --- | --- |
| `orchard_spray_valve` | millis rollover | The burst's close time is an absolute `millis()` value. A press within 400 ms of the 32-bit rollover (49.7 days of uptime) closes the valve at once. Needs `start_millis`. |
| `tank_mixer_cycle` | narrow timer | The schedule uses a 16-bit clock with absolute deadlines. Every 65.5 s of uptime the clock wraps and the mixer cycles every loop. Needs `start_millis`. |
| `door_chime_poll` | press vs sampling period | The button is polled every 30 ms and two low samples in a row are needed. A 45 ms press (the spec asks for 40 ms and up) is missed unless it happens to cover two samples. |
| `cold_store_alarm` | noise filter | The count of consecutive high samples is only reset by a clearly low sample. Brief spikes on a baseline between the two levels add up and raise the alarm. |
| `lift_call_panel` | blocking wait | The acknowledgement waits 300 ms inside `delay()`. A heartbeat that falls due during it is printed up to 300 ms late. Only presses shortly before a heartbeat show it. |
| `stair_light_timer` | two features together | The press timer and the mode switch work on their own. Changing the mode while the light is on restarts the 3 s timer. |
| `silo_fill_gauge` | accumulator overflow | The running sum of 40 ADC readings is a 16-bit `int`. Above about 4000 mm it overflows: the printed level goes negative and the lamp never lights. |
| `meadow_sprinkler_valve` | decoy | Stores an absolute close time like `orchard_spray_valve`, but compares with a signed difference, which is correct across the rollover. |
| `grain_bin_gauge` | decoy | A 16-bit `int` running sum, like `silo_fill_gauge`, but over 32 readings: the largest possible sum is 32 736, which fits. |
| `loading_dock_horn` | decoy | Blocks in `delay(60)` like `lift_call_panel`, but the heartbeat tolerance is 150 ms, so the delay can never break it. |

## Validation

Every case passes `bench.validate`: the reference compiles and passes all frozen checks in all their scenarios, the buggy sketch fails exactly the checks listed in `truth.json`, and for the decoys the sketch is the reference and fails nothing. Every check carries a `covers` line that matches a spec bullet (`bench.lint_cases`). Sketches are 68 to 103 lines in Allman style, with no hint words in names or comments.

```
backend/.venv/bin/python -m bench.lint_cases --dir practice
backend/.venv/bin/python -m bench.validate --dir practice
backend/.venv/bin/python bench/freeze_hash.py --dir practice --check
```

Scenarios in `checks.json` may set `start_millis`, the clock fast-forward, so that a short run starts near a rollover or hours into uptime.

## Plain-review baselines (reading only, no running)

One call per case, the same prompt as the benchmark's plain-review baseline, then the usual judge (`gpt-4o-mini`). Run once on 2026-11-17 to see how much reading alone finds. The cases were not changed because of these numbers. Cost: DeepSeek $0.0064, `gpt-4o-mini` $0.0054, judge $0.0037.

| Case | Planted bug | DeepSeek: found / false alarms | `gpt-4o-mini`: found / false alarms |
| --- | --- | --- | --- |
| `orchard_spray_valve` | rollover | yes / 1 | yes (a wrong reason, see below) / 1 |
| `tank_mixer_cycle` | narrow timer | yes / 2 | no / 1 |
| `door_chime_poll` | press vs sampling | yes (doubtful, see below) / 2 | no / 2 |
| `cold_store_alarm` | noise filter | yes / 0 | no / 2 |
| `lift_call_panel` | blocking wait | yes / 0 | yes / 1 |
| `stair_light_timer` | two features | yes / 1 | no / 2 |
| `silo_fill_gauge` | overflow | yes / 0 | yes / 1 |
| `meadow_sprinkler_valve` | decoy | - / 2 | - / 2 |
| `grain_bin_gauge` | decoy | - / 3 | - / 2 |
| `loading_dock_horn` | decoy | - / 2 | - / 2 |
| **Total** | 7 bugs | **7/7**, 6 false alarms on bugs, 7 on decoys | **3/7**, 10 false alarms on bugs, 6 on decoys |

- Reading finds most of these. DeepSeek names the cause in plain words for `orchard_spray_valve` ("absolute millis comparison"), `tank_mixer_cycle` (16-bit wrap), `stair_light_timer` (mode change re-arms the timer), `silo_fill_gauge` (16-bit sum) and `cold_store_alarm` (count not reset). The set is therefore not "hard to find by reading" for that model, and a result on it does not show that running the firmware adds anything over reading. It does show whether the agent's executed evidence agrees.
- Two matches the judge gave are not ones I would defend. DeepSeek's `door_chime_poll` report is about a press during the chime, not about a short press missed between samples. `gpt-4o-mini`'s `orchard_spray_valve` report is about debounce time, and the judge's own reason says it "relates to the millis() rollover". Counting only the defensible matches, DeepSeek found 6 of 7 and `gpt-4o-mini` 2 of 7.
- Every decoy drew false alarms from both models (7 and 6 in all). None of the three decoys was left alone by either model.
- One run per model and one judge pass, so a difference of one case is within noise.

## Fingerprint

Computed by `bench/freeze_hash.py --dir practice` over every file except this README. Update it here whenever a case changes.

freeze_hash.py --dir practice: `1bb18a3ac070e9e4a33f9d3d2b7b54abe98f6abae700891e1615458f8a36c8c0` (60 files)
