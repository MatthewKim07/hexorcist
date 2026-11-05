# 3-minute demo video: script and shot list

Target length 3:00, hard limit 3:00. Record at 1440x900 (the screenshots in `docs/` use the same size), browser zoom 100%, full screen, no bookmarks bar. Narration is about 390 words, so speak at a normal pace and do not rush.

## Before you record (10 minutes, do it once)

Live runs take 85 to 95 seconds, which is too long to sit through on camera, so the video cuts between a live start and runs that finished earlier. Make three runs first, from the app you will be showing (the Vultr URL if it is up, otherwise localhost:8080):

| Name | How to make it | Used in |
| --- | --- | --- |
| **Run A** | Break tab, tick "Also ask the LLM for a plain code review", click "Try the thermostat" and wait for "2 bugs cast out, 2 verified" | Shots 3 to 6 |
| **Run B** | Break tab, click "Containment demo", then "Cast the bugs out" (about 35 s, needs no API key) | Shot 7 |
| **Live take** | Nothing to prepare: shot 2 starts one on camera | Shot 2 |

Then check:

- History lists Run A and Run B. Open each once and confirm it renders instantly (the page appears in about 100 ms, there is no spinner).
- Run A has the "LLM guesses vs Hexorcist proves" panel filled in. If it shows the "Compare with a plain LLM code review" button instead, click it once and wait about 10 s, then reload.
- If a passcode is set, type it into the field at the top right before recording so it is not on camera.
- Scenario for the replay: "Threshold hover with noise (A0)". It is the first red tile in Run A.
- Do a silent dry run of the whole sequence once. Every click below must land first time.

## Timeline

| Time | On screen | Do exactly this | Say |
| --- | --- | --- | --- |
| **0:00 to 0:15** | Landing page, Break tab | Page already open on `#/`. Do not move the mouse for 4 s. Then move to the yellow "Try the thermostat" button and hold there. | "Firmware bugs don't crash with a stack trace. A fan that chatters, a button that fires twice. An LLM that reads your code will tell you: this might chatter. Hexorcist runs it, and shows you." |
| **0:15 to 0:35** | **Live take.** Run page, timeline filling in | Click "Try the thermostat". When the run page opens, hold for 5 s on the timeline: Understand turns green, then Compile. Then scroll down slowly to the scenario grid while tiles go green and red. At 0:33 cut to Shot 3. | "It reads the code and the spec, compiles the real firmware, and invents attacks: sensor noise at the threshold, glitch spikes, a disconnected sensor. Each one runs on an emulated ATmega328P, in its own sealed container." |
| **0:35 to 0:55** | **Run A**, headline | Open History, click the newest "Possessed thermostat" row. Page renders instantly. Hold on the headline and the two before and after boxes for 6 s. | "Two bugs found, two verified. Not 'might chatter': D9 toggled 23 times in five seconds, limit two. After the fix, one toggle. And a second bug the fan never mentioned: when the sensor disconnects, the fan stays off." |
| **0:55 to 1:35** | Run A, **board replay** | Click "Board replay" in the Jump bar. Pick "Threshold hover with noise (A0)" in the scenario menu if it is not selected. Click play. Let it run 4 s at 1x: fan flickers, "ON 15 toggles" counts up, serial monitor scrolls, red bands appear on the chart. Click "After fix (patch 1)". Click restart, then play. Fan stays steady. Hold on the final frame 3 s. | "This is the centerpiece. The same input, the same noisy temperature sensor, replayed on a virtual Uno. Before the fix the fan chatters, and the chart shows exactly where the requirement was violated. Now the patched firmware, same input: calm. The agent only claims a fix after recompiling and re-running every scenario, and checking nothing else broke." |
| **1:35 to 2:00** | Run A, **LLM vs Hexorcist panel** | Click "LLM vs Hexorcist" in the Jump bar. Hold 3 s on the two headers. Slowly scroll down the rows, stopping on the pair "No hysteresis" next to "Fan output chatters". Stop on the footer: "0 measured, 0 fixes tested" against "2 bugs measured, 2 fixes verified". | "Here is the same model, given the same code and spec, but only allowed to read it. It does find the problems. But every line is a guess: zero measured, none of its fixes tested. Hexorcist gives numbers, and a fix it has actually run. That is the difference between a review and a test." |
| **2:00 to 2:30** | **Run B**, containment | History, click the "Containment demo" row. Hold on the six tiles for 5 s, point the cursor along them left to right. Scroll to the "What the attacker actually got" box and hold 4 s. | "Blast Radius Zero. This upload is hostile: it includes /etc/passwd, tries to read SSH keys, carries a prompt injection, and its firmware never stops. The guard flagged it, so no model ever saw it. In the sandbox there is no network, no secrets, and the runaway firmware was killed at the thirty second limit. All five containers were destroyed. The attacker got the sandbox's own files, and nothing else." |
| **2:30 to 2:45** | README architecture diagram or slide 7 | Cut to the architecture slide. Cursor traces: Browser, control layer, sandboxes, Vultr Serverless Inference. | "The control layer holds the API key and the Docker socket, and never runs user code. Every compile and every emulation runs in a fresh container with no network, no capabilities and a read-only filesystem. A small classifier backs up the guard, and the sandbox holds even when it misses." |
| **2:45 to 3:00** | Landing page or title slide | Cut back to the landing page. Cursor on "Try the thermostat". Fade out. | "[TO CONFIRM after deploy: Hexorcist runs on a Vultr VM, with every agent call going through Vultr Serverless Inference.] Hexorcist: cast the bugs out of your firmware." |

## Notes for the edit

- The only live footage is shot 2. Everything else is a finished run, so it cannot fail on camera. Say "I started a run, and while it works here is one that finished earlier" if you want to be explicit about the cut.
- Zoom (Cmd and plus) to 125% for shots 3 and 6, where the text matters most. Return to 100% afterwards.
- Do not narrate numbers you cannot see on screen. The ones above are on screen in Run A and Run B. If a different run gives different numbers, say what the screen says.
- Two things must stay honest in the voice-over: the LLM review is one extra call that is off by default, and the guard misses most attacks (the sandbox is the real boundary). Both are in the written material, so do not oversell in the video.
- The Vultr line in the last shot is a placeholder. Until the deployment is real and the agent calls go through Vultr, cut that sentence.
