"""Previewed checks: the UNDERSTAND step on its own, and a run that reuses its output. No Docker, no LLM."""
import asyncio

from fastapi.testclient import TestClient

from app import main
from app.agent import Pipeline, normalize_assertions
from app.checks import CheckSet
from app.models import DeviceSpec, PinSpec
from app.presets import PRESETS
from tests.test_api import settings
from tests.test_fix_loop import ORIGINAL, FakeRunner, NullBus, NullStore

BODY = {"firmware": "void setup(){}\nvoid loop(){}", "behaviour": "Fan on at 30 C", "pins": [{"pin": "D9", "type": "digital_output"}]}
CHECKS = [{"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 5000, "description": "No chatter"}]


def client(monkeypatch, calls, **overrides):
    async def fake(cfg, firmware, spec):
        calls.append(spec.behaviour)
        return {"assertions": CHECKS, "device_model": {}, "warnings": []}

    monkeypatch.setattr(main, "read_checks", fake)
    return TestClient(main.create_app(settings(max_firmware_bytes=5000, max_text_bytes=500, **overrides)))


def test_preview_needs_the_passcode_and_returns_the_checks(monkeypatch):
    calls = []
    c = client(monkeypatch, calls, demo_passcode="sesame")
    assert c.post("/api/checks", json=BODY).status_code == 401
    body = c.post("/api/checks", json=BODY, headers={"X-Demo-Passcode": "sesame"}).json()
    assert body["assertions"] == CHECKS
    assert calls == ["Fan on at 30 C"]


def test_preview_is_rate_limited(monkeypatch):
    calls = []
    c = client(monkeypatch, calls, rate_limit_per_hour=2)
    codes = [c.post("/api/checks", json=BODY).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert len(calls) == 2


def test_preview_never_asks_the_model_about_a_flagged_upload(monkeypatch):
    calls = []
    c = client(monkeypatch, calls)
    hostile = {**BODY, "firmware": '#include "/etc/passwd"\nvoid setup(){}\nvoid loop(){}'}
    assert c.post("/api/checks", json=hostile).status_code == 422
    assert c.post("/api/checks", json={**BODY, "behaviour": " "}).status_code == 422
    assert calls == []


def test_preview_without_a_model_key_is_refused(monkeypatch):
    calls = []
    c = client(monkeypatch, calls, llm_api_key="")
    assert c.post("/api/checks", json=BODY).status_code == 503
    assert calls == []


def test_a_run_hands_its_checks_to_the_pipeline(monkeypatch):
    seen = []

    async def fake_run(pipeline, mode, firmware, spec, description, verdict, checks=None):
        seen.append(checks)

    monkeypatch.setattr(main, "execute_run", fake_run)
    c = TestClient(main.create_app(settings(max_firmware_bytes=5000, max_text_bytes=500, max_active_runs=5, rate_limit_per_hour=10)))
    run = {"mode": "break", **BODY, "checks": {"assertions": CHECKS, "source": "preview"}}
    assert c.post("/api/runs", json=run).status_code == 201
    assert c.post("/api/runs", json={**run, "checks": {"assertions": CHECKS, "source": "anything"}}).status_code == 422
    assert seen[0].assertions == CHECKS


class NoUnderstandLLM:
    calls: list = []

    async def json(self, system, user, schema, step):
        assert step != "understand", "the spec was read again although checks were supplied"
        return schema.model_validate({})

    async def code(self, system, user, step):
        return "void setup() {}\nvoid loop() {}\n", "No patch."


def test_a_run_with_checks_evaluates_them_without_reading_the_spec_again():
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour="x")
    pipeline = Pipeline("r", settings(max_parallel=2), FakeRunner(), NullStore(), NullBus())
    pipeline.llm = NoUnderstandLLM()
    checks = CheckSet(assertions=[*CHECKS, {"type": "max_toggles", "pin": "D4", "max_toggles": 1, "window_ms": 100}])
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, spec, checks=checks))
    assert [a["type"] for a in report["assertions"]] == ["max_toggles", "no_crash"]
    assert report["assertions"][0]["description"] == "No chatter"
    assert any("D4" in w for w in report["warnings"])
    assert report["bugs"], status


def test_every_example_ships_checks_that_survive_validation():
    for preset in PRESETS:
        if preset["id"] == "containment":
            assert "checks" not in preset
            continue
        checks = CheckSet(**preset["checks"])
        spec = DeviceSpec(pins=[PinSpec(**p) for p in preset["pins"]], behaviour=preset["behaviour"])
        kept, warnings = normalize_assertions(checks.assertions, spec)
        assert warnings == [], preset["id"]
        assert len(kept) == len(checks.assertions) + 1, preset["id"]
