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

## Hexorcist on the practice set (2026-11-18)

Two runs of the agent as of commit `6037a9c`, search off (`dev_practice_20261118T002318Z`) and search on with 30 variants per case (`dev_practice_search_20261118T003830Z`), scored with the same judge and replayed on the references. One run each, and the checks are regenerated every run, so single-case moves are within noise. No case was changed. "Honest" means a report the judge matched has a check that fails on the sketch in a scenario where the reference passes.

| Case | Planted bug | DeepSeek reading | `gpt-4o-mini` reading | Hexorcist, search off | Hexorcist, search on |
| --- | --- | --- | --- | --- | --- |
| `orchard_spray_valve` | rollover | found, 1 FA | found*, 1 FA | **found, honest**, 0 FA | found but **hollow**, 0 FA |
| `tank_mixer_cycle` | 16-bit wrap | found, 2 FA | missed, 1 FA | found but **hollow**, 0 FA | found but **hollow**, 0 FA (see below) |
| `door_chime_poll` | press vs sampling | found*, 2 FA | missed, 2 FA | **found, honest**, 0 FA | missed, 0 FA |
| `cold_store_alarm` | noise filter | found, 0 FA | missed, 2 FA | missed, 0 FA | found, honest (weak, see below), 0 FA |
| `lift_call_panel` | blocking wait | found, 0 FA | found, 1 FA | **found, honest**, 1 FA | **found, honest**, 1 FA |
| `stair_light_timer` | two features | found, 1 FA | missed, 2 FA | **found, honest**, 0 FA | **found, honest**, 0 FA |
| `silo_fill_gauge` | overflow | found, 0 FA | found, 1 FA | missed, 0 FA | missed, 0 FA |
| `meadow_sprinkler_valve` | decoy | 2 FA | 2 FA | 1 report, patched | 1 report, patched |
| `grain_bin_gauge` | decoy | 3 FA | 2 FA | **nothing reported** | **nothing reported** |
| `loading_dock_horn` | decoy | 2 FA | 2 FA | **nothing reported** | **nothing reported** |
| **Total** | 7 bugs | 7/7 (6 defensible), 6 FA on bugs, 7 on decoys | 3/7 (2 defensible), 10 and 6 | 5/7, honest 4/7, FA 1 on bugs and 1 on decoys | 5/7, honest 3/7, FA 1 and 1 |

\* A judge match that is not defensible, see the baseline notes above.

Verified fix on the frozen checks: 4/7 in both runs. The search-off run claimed 6 `fixed` and 5 pass the frozen checks (the `tank_mixer_cycle` claim does not). The search run claimed 4 and 3 pass (`orchard_spray_valve` does not). Cost $0.037 and $0.047 for ten cases, 15 and 22 minutes in all, plus $0.003 for the judge. Both ran with mixed clean rooms (`deepseek-chat` and `gpt-4o-mini`, no fallback, no skipped room) in the cases that needed them: 8 and 7.

**What the practice set shows.**
- **False alarms are where running the firmware pays off here.** Against 13 (DeepSeek) and 16 (`gpt-4o-mini`) false alarms for plain reading, the agent reported 1 on the bugs and 1 on the decoys in each run. `grain_bin_gauge` and `loading_dock_horn` drew no report at all. The one decoy report in both runs, on `meadow_sprinkler_valve` (a class B check: the reference fails it), also led the agent to patch a correct sketch, so that decoy was not left alone.
- **Reading found more of the bugs than running did.** DeepSeek named 6 or 7 of the 7. The agent found 5 of 7, of which 4 (search off) and 3 (search on) were honest.
- **`silo_fill_gauge` is lost to the clean rooms in both runs.** Both rooms print about 859 mm where the probe reads 4200 mm: they print raw ADC counts and ignore "1 mV per mm". The two checks that catch the overflow (`a2`, `a3`) fail on both rooms the same way and are dropped as unconfirmed, although they pass on the reference. This is the same correlated clean-room error as `glue_solenoid_short`, across two different models.
- **`tank_mixer_cycle`, search on:** the judge matched the planted bug to `a1`, a pulse check that the reference also fails (hollow). The run also reported `a2`, a print-period check that fails only in `llm-7` (`start_millis` 191808, where the 16-bit clock wraps) and passes on the reference. So the wrap was found honestly by the clock fast-forward, which the scorer's matching rule does not credit.

- **`cold_store_alarm`, search on:** the honest detection rests on a pulse-length check that fails in one scenario (`llm-3`, "lasted 40 ms, expected 300"). It is a generous match to the planted spike-accumulation bug.

**Search findings: none.** 300 variants ran (30 per case, none over budget). No variant broke a check that had not already failed, so nothing reached the gates: the three gate counts (a, b, c) are 0, 0, 0 in every case and nothing was rejected. In six cases some variants broke checks that were already failing (cold_store 10, lift_call 16, meadow 3, orchard 2, stair 14, tank_mixer 48); by design those are not findings.

**Was any bug found only because of search or the clock fast-forward?**
- **Search:** no bug.
- **Clock fast-forward in the attack plan:** `orchard_spray_valve` in the search-off run. The check fails honestly in one scenario only, `llm-2`, which starts the clock at 4294967240. In the search run the model's clock scenarios started elsewhere, the planted check was already failing for an unrelated reason (an 8 ms press that the reference also misses), and the bug was missed. `tank_mixer_cycle` in the search run is the second case (`llm-7`, above). The model added `start_millis` scenarios in 9 of 10 cases without search and in all 10 with it, and none of the three decoys drew a false report from them.
- **Search variants that start the clock late (`uptime`, 4 to 11 per case):** none exposed a bug. I replayed the 30 orchard variants offline: the `uptime` variant `search-9` only broke the already-failing 8 ms check. The variants move the wrap into the run but leave the presses where they were, so a burst falls in the 400 ms before the wrap only by chance. Whether to align the wrap with an input event is a change I have not made.

## Hexorcist with the room-facts prompt, all ten cases (`dev_practice2_20261118T063831Z`, 2026-11-18)

The full practice set with the clean rooms writing a `// SPEC FACTS` block first (search off), against the two earlier runs. One run each, no case changed.

**Audit.** No error rows, nothing missing, mixed rooms with no fallback. Cross-check ran in 8 cases with room 1 on `deepseek-chat` and room 2 on `gpt-4o-mini`, ready every time (16 of 16 rooms carry the `SPEC FACTS` block and call `Serial.begin`). 2 cases needed no room (0 calls, $0 OpenAI). Spend: DeepSeek $0.0485, OpenAI $0.0037, in all $0.052, plus about $0.0014 for the judge.

| Case | Planted bug | Search off (earlier run) | Search on (earlier run) | **Room facts, search off** |
| --- | --- | --- | --- | --- |
| `orchard_spray_valve` | rollover | honest | hollow | hollow, status `partial` |
| `tank_mixer_cycle` | 16-bit wrap | hollow | hollow | hollow, 1 false alarm |
| `door_chime_poll` | press vs sampling | honest | missed | honest |
| `cold_store_alarm` | noise filter | missed (`a1` unconfirmed) | honest (weak) | missed (`a1` unconfirmed, fails on the reference) |
| `lift_call_panel` | blocking wait | honest, 1 false alarm | honest, 1 | honest, 1 (`partial`) |
| `stair_light_timer` | two features | honest | honest | honest |
| `silo_fill_gauge` | overflow | missed (`a2`, `a3` unconfirmed, pass on the reference) | missed (same) | **honest, `fixed`** |
| `meadow_sprinkler_valve` | decoy | 1 report | 1 report | 1 report |
| `grain_bin_gauge` | decoy | nothing | nothing | nothing |
| `loading_dock_horn` | decoy | nothing | nothing | nothing |

| | Search off | Search on | Room facts |
| --- | ---: | ---: | ---: |
| Recall | 5/7 | 5/7 | **6/7** |
| Honest recall | 4/7 | 3/7 | 4/7 |
| False alarms (bugs + decoys) | 1 + 1 | 1 + 1 | 2 + 1 |
| Verified fix on frozen checks | 4/7 | 4/7 | 4/7 |
| `fixed` claims that pass the frozen checks | 5/6 | 3/4 | 4/4 |
| Unconfirmed checks | 6 | 3 | 3 |
| ...of which pass on the reference | 2 | 2 | **0** |
| Cost / time | $0.037, 15 min | $0.047, 22 min | $0.052, 17 min |

- **`silo_fill_gauge` is found and fixed** now that the rooms convert the scale, and no unconfirmed check passes on the reference any more. This is the targeted effect, and it held at full-set scale.
- **`orchard_spray_valve` is fragile.** It was found honestly only in the run whose model-written clock scenario started at 4294967240, and is hollow in the other two. `tank_mixer_cycle` stays hollow in all three. The rooms do not change either: they depend on whether the model's `start_millis` scenarios land a press just before the wrap.
- **False alarms:** the three are all class B (`lift_call_panel` a1, `meadow_sprinkler_valve` a1, `tank_mixer_cycle` a4). The `loading_dock_horn` false alarm of the five-case room-facts run did not come back here, so that one was regenerated-check noise, not the prompt. `tank_mixer_cycle` drew a class B false alarm in both room-facts runs (a1, then a4) and in neither earlier run, so that case may be a real side effect of the prompt, or chance; two runs cannot tell.
- **Decoys:** `grain_bin_gauge` and `loading_dock_horn` drew no report; `meadow_sprinkler_valve` drew one and was patched, as in every run.

## Fingerprint

Computed by `bench/freeze_hash.py --dir practice` over every file except this README. Update it here whenever a case changes.

freeze_hash.py --dir practice: `1bb18a3ac070e9e4a33f9d3d2b7b54abe98f6abae700891e1615458f8a36c8c0` (60 files)
