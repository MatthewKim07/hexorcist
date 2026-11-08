# Slide outline: 8 slides

Plain light-on-dark slides in the app's own look (near-black background, off-white text, one indigo accent, green for measured, red for failures). One idea per slide, at most three lines of text each. Screenshots come from `docs/`. Speaker notes are one or two sentences.

## 1. Problem: firmware bugs do not crash

- Title: **Is your firmware possessed?**
- A fan that chatters at a threshold. A button that fires twice. A logger that lies. An alarm that goes deaf during a `delay()`.
- All of them compile. All of them look fine when you read the code.
- Visual: `docs/landing.png`, or three one-line symptoms with an icon each.
- Notes: this is the class of bug that survives code review, because the code is plausible. You only see it when it runs.

## 2. Why LLM review isn't enough

- Title: **A guess is not a measurement**
- Left: the model reading the code, "this might chatter", six concerns, 0 measured, 0 fixes tested. Right: `D9 toggled 23 times in a 5000 ms window (limit 2)`, 2 bugs measured, 2 fixes verified.
- Visual: `docs/llm-vs-hexorcist.png`, cropped to the two headers and the "No hysteresis" row.
- Notes: be fair to the model. It finds many of the same problems. What it cannot do is measure them, or tell you whether its own fix works. That gap is the product.

## 3. How it works

- Title: **The model proposes. The engine judges.**
- Pipeline in one row: Understand, Compile, Attack plan, Execute, Diagnose, Fix, Verify, Report.
- Three callouts: real compiler output and emulator traces feed the loop; verdicts come from deterministic Python, never from the LLM; a fix is claimed only if everything that failed now passes and nothing new broke.
- Visual: the five-stage stepper from a live run, or the verdict and board at the top of `docs/run-result.png`.
- Notes: up to three fix attempts, each re-run against the entire suite, and patches that go back to a disproven approach are rejected.

## 4. Live results

- Title: **Five presets, real model, all green**
- The results table from the README: thermostat 2 of 2, button 1 of 1, logger 1 of 1, alarm 3 of 3, containment 11 of 11, in 33 to 90 s.
- Visual: the table on the left, `docs/hexorcist-replay.gif` (or two stills: before and after) on the right.
- Notes: the exact numbers change between runs because the model designs part of the attack. The verdicts do not. Say that the button needed two patch attempts: the loop is real.

## 5. Containment: Blast Radius Zero

- Title: **Hostile in, nothing out**
- Six checks in one row: guard flagged it, LLM never saw it, no network, no secrets, timeout kill, containers removed.
- Numbers: 138 containers created and 138 removed, 0 secrets found, runaway firmware killed at 30 s.
- Visual: `docs/containment.png`.
- Notes: the attacker's `#include "/etc/passwd"` did read a file, the sandbox's own. Say that plainly. The UI says it too, and shows what the attacker actually got.

## 6. ML guard, honestly

- Title: **A second layer, not the wall**
- Table: regex only (recall 13%, new styles 10%), shipped regex plus TF-IDF (recall 49%, new styles 39%, false positive rate 3.4%, 2 ms), MiniLM (recall 71%, false positive rate 7.0%, 214 ms, not shipped).
- One line of caveats: catches under half of attacks, synthetic data, test set looked at twice. The sandbox is the boundary.
- Visual: the table from the README.
- Notes: we shipped the weaker model on purpose, because a blocking gate needs its false positive rate to hold on unseen code, and MiniLM flagged 17% of real Arduino sketches.

## 7. Architecture on Vultr

- Title: **Control layer outside, sandboxes inside**
- Diagram: Browser, nginx and Caddy, the control layer (holds the LLM key and the Docker socket, never runs user code), per-task sandbox containers, Vultr Serverless Inference.
- Three facts: one fresh container per compile and per scenario; LLM chosen by three environment variables; passcode, rate limits, ufw, and only Caddy publishes ports.
- Visual: the Mermaid diagram from the README, redrawn with Vultr branding colours if you like.
- Notes: [TO CONFIRM after deploy] say where it runs only once it does. Until then: "ready to deploy on a Vultr VM, kit included".

## 8. What's next

- Title: **From emulated Uno to real fleets**
- More chips and peripherals (I2C, SPI), so more of the firmware people actually ship can be attacked.
- Run the model-written attack plans of past runs as a regression suite on every commit.
- A stronger guard model in its own process, and testing the LLM's own suggested fix in the comparison panel.
- Retune and measure on Vultr's models.
- Closing line: **Cast the bugs out of your firmware.** Repository and demo link.
