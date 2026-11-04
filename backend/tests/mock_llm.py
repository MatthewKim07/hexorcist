"""A scripted OpenAI-compatible server for testing the pipeline without an API key.

TEST ONLY. Replies are canned, so a run against this says nothing about what a real
model would do. It proves the plumbing, the loop and the verification logic.

Run: python -m uvicorn tests.mock_llm:app --port 9199
Modes, selected by the model name:
  mock           a correct patch first time
  mock-badjson   malformed JSON first, to exercise the repair retry
  mock-regress   a first patch that does not compile, then one with the bug, then correct
Build mode replies with a sketch that does not compile, then the correct one.
"""
from __future__ import annotations

import json
import re
import time

from fastapi import FastAPI, Request

from tests.fixtures import ASSERTIONS, CORRECT_FIRMWARE

app = FastAPI()
attempts: dict[str, int] = {}
bad_json_served: set[str] = set()

SIGNATURES = {
    "thermostat": "Thermostat fan controller",
    "button": "Push button toggles an LED",
    "logger": "Temperature logger",
    "alarm": "Panic alarm",
}


def identify(text: str) -> str:
    for preset, marker in SIGNATURES.items():
        if marker in text:
            return preset
    return "thermostat"


def reply(content: str) -> dict:
    return {
        "id": "mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


def attack_for(preset: str) -> list[dict]:
    if preset in ("button", "alarm"):
        return [
            {
                "name": "Hard bounce on a long press",
                "hypothesis": "Long bounce near the debounce window",
                "seed": 7,
                "duration_ms": 6000,
                "digital": [{"pin": "D2", "initial": 1, "events": [{"t_ms": 1200, "value": 0, "bounce_ms": 15, "bounce_count": 9}, {"t_ms": 2000, "value": 1, "bounce_ms": 15, "bounce_count": 9}]}],
            },
            {"name": "Scenario with an unknown pin", "hypothesis": "should be dropped", "digital": [{"pin": "D7", "initial": 1}]},
        ]
    return [
        {
            "name": "Slow drift through the band",
            "hypothesis": "Drift across the thresholds with noise",
            "seed": 9,
            "duration_ms": 6000,
            "analog": [{"pin": "A0", "segments": [{"t_ms": 0, "mv": 200}, {"t_ms": 6000, "mv": 400}], "noise_mv": 3}],
        },
        {"name": "Malformed scenario", "hypothesis": "should be dropped", "analog": [{"pin": "Z9", "segments": []}]},
    ]


@app.post("/v1/chat/completions")
async def completions(request: Request) -> dict:
    body = await request.json()
    model = body.get("model", "mock")
    messages = body["messages"]
    system = messages[0]["content"]
    user = messages[1]["content"]
    preset = identify(user)

    if "requirements engineer" in system:
        if model == "mock-badjson" and preset not in bad_json_served:
            bad_json_served.add(preset)
            return reply('{"device_model": {"summary": "oops", "assertions": [')
        assertions = ASSERTIONS[preset] + [{"type": "max_toggles", "pin": "D99", "max_toggles": 1, "window_ms": 1}]
        return reply(json.dumps({"device_model": {"summary": f"Mock model of {preset}", "inputs": [], "outputs": [], "thresholds": [], "risks": ["Scripted test reply"]}, "assertions": assertions}))

    if "adversarial firmware tester" in system:
        return reply("```json\n" + json.dumps({"scenarios": attack_for(preset)}) + "\n```")

    if "explaining failures" in system:
        ids = re.findall(r'"assertion_id": "(a\d+)"', user)
        bugs = [{"assertion_id": i, "title": f"Scripted bug {i}", "severity": "high", "root_cause": "Scripted test explanation.", "code_lines": [1, 9999]} for i in ids]
        return reply(json.dumps({"bugs": bugs}))

    if "patching Arduino firmware" in system:
        key = f"{model}:{preset}"
        attempts[key] = attempts.get(key, 0) + 1
        n = attempts[key]
        correct = CORRECT_FIRMWARE[preset]
        if model == "mock-regress" and n == 1:
            return reply("This one will not compile.\n```cpp\nvoid setup() { oops(); }\nvoid loop() {}\n```")
        if model == "mock-regress" and n == 2:
            return reply("Adds a comment and changes nothing.\n```cpp\n// Thermostat fan controller, attempt two\n" + _first_preset_firmware(preset) + "```")
        return reply(f"Applies the reference fix.\n```cpp\n{correct}```")

    if "firmware architect" in system:
        preset_data = _preset("thermostat")
        return reply(json.dumps({"title": "Scripted thermostat", "pins": preset_data["pins"], "behaviour": preset_data["behaviour"]}))

    if "Write complete Arduino firmware" in system:
        if "failed to compile" not in user:
            return reply("```cpp\nvoid setup() { oops(); }\nvoid loop() {}\n```")
        return reply(f"```cpp\n{CORRECT_FIRMWARE['thermostat']}```")

    return reply("{}")


def _preset(preset: str) -> dict:
    from app.presets import PRESETS

    return next(p for p in PRESETS if p["id"] == preset)


def _first_preset_firmware(preset: str) -> str:
    return _preset(preset)["firmware"]
