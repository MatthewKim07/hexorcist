# lablab.ai submission text: Hexorcist

Everything here is ready to paste, except the items in the checklist at the bottom, which only you can fill in.

## Title

Hexorcist: cast the bugs out of your firmware

## Short description (249 characters, limit 255)

Hexorcist is an AI QA engineer for firmware. It compiles your Arduino sketch, attacks it on an emulated ATmega328P in sealed per-task sandboxes, reports bugs with measured evidence, and proves its own fix by re-running everything. Blast Radius Zero.

## Long description

**The problem.** Firmware bugs rarely crash. A fan that chatters when the temperature hovers at a threshold, a button that toggles twice per press, a sensor logger that is off by 46 degrees, an alarm that goes deaf while a delay() blocks: all of them compile, and all of them look fine when you read the code. An LLM that reads the code will say "this might chatter." That is a guess, and the team still has to find out whether it is true.

**What Hexorcist does.** You hand it an Arduino sketch and a plain-English description of the wiring and what the device should do. The agent turns the spec into machine-checkable assertions, compiles the real firmware, and invents adversarial scenarios for that specific code: noise at a threshold, glitch spikes, a disconnected or floating sensor, button bounce, rapid changes, out-of-range values. Every scenario runs against the compiled binary on an emulated ATmega328P (simavr), in parallel, each in its own disposable container. A deterministic evaluator checks the traces. The result is a bug report with evidence like "D9 toggled 23 times in a 5000 ms window (limit 2)", the root cause with code lines, a minimal patch, and proof: Hexorcist recompiles, re-runs the entire suite, and only claims a fix if everything that failed now passes and nothing else broke. The fix is replayed on an animated virtual Arduino Uno, with a Before and After toggle on the same input.

**The model proposes, the engine judges.** The LLM writes assertions, attack scenarios, explanations and patches. It never decides whether anything passed. Verdicts and evidence strings come from plain Python evaluating the emulator trace. If the spec cannot be turned into checks, the run is reported as inconclusive, never as clean.

**Agentic loop with real feedback.** Understand, compile, attack plan, execute, diagnose, fix, verify, report. Compiler errors and emulator traces feed back into the loop. The fix step can retry up to three times, builds on the best measured patch, and rejects patches that go back to an approach that was already disproven. A Build mode writes firmware from a description and then has to survive the same attack before it may declare success. It has already found a real bug in our own emulator harness.

**LLM guesses vs Hexorcist proves.** On any run you can switch on a side panel that gives the same model the same firmware as a plain code review, with no emulator, and shows its answer next to the measured evidence. A modern model does find many of the same problems. It cannot measure them or test its own suggested fix. In our thermostat run it raised 6 concerns, none measured and none of its fixes tested, while Hexorcist measured 2 bugs and verified 2 fixes. It is one extra call, clearly labelled, and off by default.

**Blast Radius Zero.** Uploaded and AI-written code compiles and runs only inside per-task sandbox containers: no network, an empty environment with no secrets, all capabilities dropped, no-new-privileges, a non-root user, a read-only root filesystem, tmpfs scratch space that cannot execute, no host mounts, no Docker socket, memory, CPU and process limits, and a hard wall-clock kill enforced from outside. Limits shown in the UI are read back from docker inspect, not from what was requested. The control layer holds the API key and the Docker socket and never runs user code. A built-in containment demo uploads a hostile project (host file includes, a prompt injection, firmware that never stops) and shows the guard flagging it, the LLM never being contacted, no secrets leaking, the runaway firmware killed at 30 seconds, and every container destroyed: 11 of 11 checks. Across the five presets in our latest run, 138 containers were created, 138 removed, and 0 secrets were found in any sandbox output.

**An ML guard, honestly measured.** A small trained classifier (TF-IDF and logistic regression, 398 KiB, about 2 ms per upload) backs up the regex rules that screen uploads. It raises recall on unseen attack styles from 10% to 39% at a 3.4% false positive rate. It still misses most attacks, so the sandbox does not rely on it. A fine-tuned MiniLM scored better but flagged 17% of real Arduino library sketches at its threshold and is 100 times slower, so we shipped the baseline and documented why.

**Results.** On the five presets with a real model, every one reached its expected state: thermostat 2 of 2 bugs verified, button 1 of 1, logger 1 of 1, alarm 3 of 3, and the containment demo 11 of 11 checks, in 33 to 90 seconds each. The exact numbers vary between runs because the model designs part of the attack; the verdicts do not.

**Architecture.** A React front end with an animated virtual board, a FastAPI control layer, per-task sandbox containers (arduino-cli, simavr, and a small C harness that injects voltages, bounce and floating pins), SQLite for runs and traces, and server-sent events for every agent step. The LLM is any OpenAI-compatible endpoint chosen only by environment variables, so the agent calls go through Vultr Serverless Inference by changing `.env`. A deploy kit for a Vultr VM is included: Docker, ufw, Caddy with automatic HTTPS, a required demo passcode and rate limits.

**Known limits.** Arduino Uno only, sensors modelled as pin voltages, no I2C or SPI. Prompts were tuned on one model. Emulation is about 1.5x realtime on one core. The guard catches under half of hostile uploads. These are listed in the README.

## Tags

AI agents, firmware, embedded systems, Arduino, QA, testing, emulation, simavr, sandboxing, containers, security, Vultr, Vultr Serverless Inference, Blast Radius Zero, FastAPI, React, LLM, prompt injection, hardware-in-the-loop, developer tools

## Links to fill in

- Public repository: https://github.com/MatthewKim07/hexorcist (branch `hexorcist-mvp`, you push it)
- Live demo: [Vultr URL, plus the demo passcode in the "how to try it" field]
- Video: [YouTube or Loom link]
- Slides: built from `docs/submission/slides.md`

## Before you submit (only you can do these)

- [ ] Push `hexorcist-mvp` to GitHub and make the repository public.
- [ ] Deploy on a Vultr VM and point `.env` at Vultr Serverless Inference. Then rerun `run_presets --repeat 2` on the VM, since the prompts were tuned on DeepSeek. Update the results table in the README with those numbers.
- [ ] Until that is done, the sentences "agent calls go through Vultr Serverless Inference" and "deployed on Vultr" are not yet true. Keep them out of the form and the video, or word them as "ready to deploy".
- [ ] Record the video from `video-script.md`, upload it, paste the link.
- [ ] Set `DEMO_PASSCODE` on the public demo, and put it in the submission's testing instructions. The LLM review panel is also passcode-protected there.
- [ ] Re-check the numbers in the long description against the README after the Vultr run.
