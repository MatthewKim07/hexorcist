<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/brand/hexorcist-dark.svg" />
    <img src="frontend/public/brand/hexorcist-light.svg" alt="Hexorcist logo" height="72" />
  </picture>
</p>

<h1 align="center">Hexorcist</h1>

<p align="center">An AI agent that attacks Arduino firmware on an emulated chip, then proves its own fix.</p>

<p align="center">
  <img src="docs/images/hero.png" alt="Finished thermostat report: verdict, stats, and board replay" width="900" />
</p>

## Why

Firmware bugs like a fan that chatters at a threshold or a button that double-toggles often compile cleanly and look plausible when you only read the sketch. A code review can guess; Hexorcist compiles the firmware, runs it on an emulated chip under adversarial inputs, and measures what happened.

## What it does

- Finds bugs by compiling the sketch and running it under adversarial conditions on an emulated ATmega328P.
- Reports measured evidence from the emulator trace, for example `D9 toggled 23 times in a 5000 ms window (limit 2)`.
- Writes a minimal patch and only calls the run fixed after re-running the full scenario suite with nothing new broken.
- Write firmware mode: generates a sketch from a description, then has to survive the same attacks before it is accepted.

## How it works

```mermaid
flowchart LR
  S[Spec + sketch] --> A[Assertions]
  A --> P[Attack scenarios]
  P --> C[Compile]
  C --> E[Emulate in sealed containers]
  E --> J[Deterministic judge]
  J --> D[Diagnose]
  D --> F[Patch]
  F --> V[Verify full suite]
  V --> R[Report]
```

**The model proposes; the engine judges.**

The LLM invents assertions, scenarios, root-cause notes, and patches. Every pass or fail comes from plain Python that evaluates the harness JSON against those assertions. Evidence strings are built from pin events and serial logs, not from model text. A model cannot talk a failure into a pass, and a fix is claimed only when the same judge re-runs the whole suite on the patched firmware.

## Results

Three runs of each buggy preset through the live API on 2026-11-14, model `deepseek-chat` (DeepSeek), via `python -m scripts.run_presets --repeat 3`. Out of 3 runs per preset, all 12 reached a verified fix. Containment was run once (11/11 checks). Scenario names and patch sizes still vary because the model designs part of the attack.

| Preset | Bug type | Bugs found | Fixed and verified (runs) | Median time |
| --- | --- | ---: | ---: | ---: |
| Thermostat without hysteresis | No hysteresis; no sensor fault check | 2 | 3/3 | 116 s |
| Button without debounce | No debounce | 1 | 3/3 | 43 s |
| Sensor logger with wrong units | Wrong unit conversion | 1 | 3/3 | 79 s |
| Alarm with blocking delay | Blocking `delay()` | 3 | 3/3 | 59 s |
| Containment test | Hostile upload | — | 1/1 (11/11 checks) | 32 s |

## Sandbox

Every compile and every scenario run gets a fresh container that is always removed afterwards. Limits (from `backend/app/sandbox.py` and `backend/app/config.py`):

- `--network none` / `network_disabled`
- empty environment (no secrets)
- `cap_drop: ALL`, `no-new-privileges:true`
- non-root `USER 1000:1000` in the image
- read-only root filesystem
- tmpfs `/work` and `/tmp` (`noexec,nosuid,nodev`, 128 MiB)
- memory 512 MiB, no swap; 1 CPU; `pids_limit` 128
- wall-clock kill: compile 60 s, emulate 30 s
- Docker socket never mounted into a sandbox

<p align="center">
  <img src="docs/images/containment.png" alt="Containment report: 11/11 checks, 0 secrets, containers removed" width="900" />
</p>

The containment demo is a hostile sketch and a prompt-injection spec. It never calls the LLM; the measured run above passed 11/11 checks in 32 s.

## Prompt-injection guard

`screen_request` combines regex rules with a shipped TF-IDF + logistic regression classifier (`backend/app/guard_model.json`). On the held-out test set (`ml/results.json`, `ml/README.md`):

- regex alone: **10%** recall on new attack styles
- regex + TF-IDF: **39.4%** recall on new styles, **3.4%** FPR, ~**2.2 ms** p50 per upload

A fine-tuned MiniLM scored higher recall but flagged **17%** of real Arduino library sketches at its threshold (and ~214 ms p50), so it was not shipped. The guard still misses most attacks; the sandbox is the real boundary.

## Compared to

- **A plain LLM code review.** The same model can flag likely bugs by reading the sketch. It cannot measure them on a trace or re-run a patch. The Compare tab puts that review next to Hexorcist's measured evidence on a Break run.
- **Wokwi and simavr.** Useful simulators and CI runners when you write the tests yourself. Hexorcist sits on top of simavr: it turns a plain-English spec into checks, invents attacks, and verifies its own patch.

## Screenshots

<p align="center">
  <img src="docs/images/start.png" alt="Home page with presets" width="900" />
</p>

<p align="center">
  <img src="docs/images/replay.gif" alt="Board replay: Before chatter, then After steady" width="900" />
</p>

<p align="center">
  <img src="docs/images/mobile.png" alt="Thermostat report on a narrow viewport" width="390" />
</p>

## Run it locally

Prerequisites: Docker with Compose v2.

```bash
git clone https://github.com/MatthewKim07/hexorcist.git
cd hexorcist
cp .env.example .env
# Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL to any OpenAI-compatible endpoint.
# Compose builds the sandbox image (arduino-cli + simavr), then the backend and frontend.
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080) (or the port in `HEXORCIST_PORT`). `GET /api/health` should return `"ok": true`. Without an API key the UI still loads; Break/Build runs that need the model will fail until one is set. The containment preset does not need a model.

## Tech stack

- **Frontend:** React, Vite, TypeScript, Tailwind
- **Backend:** FastAPI, SQLite, SSE
- **Sandbox:** per-task Docker containers, `arduino-cli` inside
- **Emulator:** simavr + custom AVR harness (`sandbox/harness`)
- **ML:** regex + TF-IDF / logistic regression guard (stdlib inference)

## Limitations

- Arduino Uno (ATmega328P) only
- Sensors modelled as pin voltages; no I2C or SPI peripherals
- Prompts tuned mainly on one chat model
- Emulation measured at about **1.3× real time** alone on this machine (`scripts/measure_speed`: 8000 ms simulated in 6033 ms wall-clock); long scenarios must still fit the 30 s wall-clock kill
- The input guard catches under half of held-out attacks

## License

[MIT](LICENSE)
