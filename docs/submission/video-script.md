# 3-minute demo video: script and shot list

Target length 3:00, hard limit 3:00. Record at 1440x900 (the screenshots in `docs/` use the same size), browser zoom 100%, full screen, no bookmarks bar. Narration is about 390 words, so speak at a normal pace and do not rush.

## Before you record (10 minutes, do it once)

Live runs take 85 to 95 seconds, which is too long to sit through on camera, so the video cuts between a live start and runs that finished earlier. Make three runs first, from the app you will be showing (the Vultr URL if it is up, otherwise localhost:8080):

| Name | How to make it | Used in |
| --- | --- | --- |
| **Run A** | Break tab, "Paste your own firmware", tick "Add a plain LLM review", click "Run" (the thermostat is already loaded) and wait for "2 bugs found · 2 fixed and verified" | Shots 3 to 6 |
| **Run B** | Break tab, "Paste your own firmware", pick "Containment test", then "Run" (about 35 s, needs no API key) | Shot 7 |
| **Live take** | Nothing to prepare: shot 2 starts one on camera | Shot 2 |

Then check:

- History lists Run A and Run B. Open each once and confirm it renders instantly (the page appears in about 100 ms, there is no spinner).
- Run A has the Compare tab filled in. If it shows the "Run a plain LLM review" button instead, click it once and wait about 10 s.
- If a passcode is set, type it into the field at the top right before recording so it is not on camera.
- Scenario for the replay: "Threshold hover with noise (A0)". The board opens on it by default, because chatter has the most visual evidence.
- Do a silent dry run of the whole sequence once. Every click below must land first time.

## Timeline

| Time | On screen | Do exactly this | Say |
| --- | --- | --- | --- |
| **0:00 to 0:15** | Landing page, Break tab | Page already open on `#/`. Do not move the mouse for 4 s. Then move to the "Try the thermostat" button and hold there. | "Firmware bugs don't crash with a stack trace. A fan that chatters, a button that fires twice. An LLM that reads your code will tell you: this might chatter. Hexorcist runs it, and shows you." |
| **0:15 to 0:35** | **Live take.** Run page, stepper filling in | Click "Try the thermostat". When the run page opens, hold for 5 s on the stepper: Understand, Attack, then Measure with the scenario count climbing. At 0:33 cut to Shot 3. | "It reads the code and the spec, compiles the real firmware, and invents attacks: sensor noise at the threshold, glitch spikes, a disconnected sensor. Each one runs on an emulated ATmega328P, in its own sealed container." |
| **0:35 to 0:55** | **Run A**, headline | Open History, click the newest "Thermostat without hysteresis" row (older rows in History keep their old names). Page renders instantly. Hold on the headline, then open the "Fan output chatters" row for 4 s. | "Two bugs found, two verified. Not 'might chatter': D9 toggled 23 times in five seconds, limit two. After the fix, one toggle. And a second bug the fan never mentioned: when the sensor disconnects, the fan stays off." |
| **0:55 to 1:35** | Run A, **board replay** | The board opens on "Threshold hover with noise (A0)", the chatter bug. Click play. Let it run 4 s at 1x: the fan flickers and "ON 15 toggles" counts up. Open "Signal trace" to show the red bands on the chart if there is time. Click "After". Click play again. Fan stays steady. Hold on the final frame 3 s. | "This is the centerpiece. The same input, the same noisy temperature sensor, replayed on a virtual Uno. Before the fix the fan chatters, and the chart shows exactly where the requirement was violated. Now the patched firmware, same input: calm. The agent only claims a fix after recompiling and re-running every scenario, and checking nothing else broke." |
| **1:35 to 2:00** | Run A, **Compare tab** | Click the "Compare with plain LLM" tab. Hold 3 s on the two headers. Stop on the pair "No hysteresis" next to "Fan output chatters". Stop on the last line: "0 measured · 0 fixes tested" against "2 measured · 2 fixes verified". | "Here is the same model, given the same code and spec, but only allowed to read it. It does find the problems. But every line is a guess: zero measured, none of its fixes tested. Hexorcist gives numbers, and a fix it has actually run. That is the difference between a review and a test." |
| **2:00 to 2:30** | **Run B**, containment | History, click the newest "Containment test" row. Hold on the row of six checks for 5 s, point the cursor along them left to right, and click "No network". Scroll down to "What the attacker got" (no tab to open) and hold 4 s. | "Blast Radius Zero. This upload is hostile: it includes /etc/passwd, tries to read SSH keys, carries a prompt injection, and its firmware never stops. The guard flagged it, so no model ever saw it. In the sandbox there is no network, no secrets, and the runaway firmware was killed at the thirty second limit. All five containers were destroyed. The attacker got the sandbox's own files, and nothing else." |
| **2:30 to 2:45** | README architecture diagram or slide 7 | Cut to the architecture slide. Cursor traces: Browser, control layer, sandboxes, Vultr Serverless Inference. | "The control layer holds the API key and the Docker socket, and never runs user code. Every compile and every emulation runs in a fresh container with no network, no capabilities and a read-only filesystem. A small classifier backs up the guard, and the sandbox holds even when it misses." |
| **2:45 to 3:00** | Landing page or title slide | Cut back to the landing page. Cursor on "Try the thermostat". Fade out. | "[TO CONFIRM after deploy: Hexorcist runs on a Vultr VM, with every agent call going through Vultr Serverless Inference.] Hexorcist: cast the bugs out of your firmware." |

## Notes for the edit

- The only live footage is shot 2. Everything else is a finished run, so it cannot fail on camera. Say "I started a run, and while it works here is one that finished earlier" if you want to be explicit about the cut.
- Zoom (Cmd and plus) to 125% for shots 3 and 6, where the text matters most. Return to 100% afterwards.
- Do not narrate numbers you cannot see on screen. The ones above are on screen in Run A and Run B. If a different run gives different numbers, say what the screen says.
- Two things must stay honest in the voice-over: the LLM review is one extra call that is off by default, and the guard misses most attacks (the sandbox is the real boundary). Both are in the written material, so do not oversell in the video.
- The Vultr line in the last shot is a placeholder. Until the deployment is real and the agent calls go through Vultr, cut that sentence.
