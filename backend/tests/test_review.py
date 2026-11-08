"""The optional plain code review. Nothing here touches an LLM or a sandbox."""
import time

from fastapi.testclient import TestClient

from app import main, review
from app.models import DeviceSpec
from app.prompts import ReviewConcern, ReviewReply

from tests.test_api import settings

FIRMWARE = "void setup()\n{\n}\nvoid loop()\n{\n}\n"
RUN = {"mode": "break", "firmware": FIRMWARE, "behaviour": "x", "pins": []}


async def no_pipeline(*args, **kwargs):
    return None


def client(monkeypatch, fake_review=None, **overrides):
    monkeypatch.setattr(main, "execute_run", no_pipeline)
    if fake_review is not None:
        monkeypatch.setattr(main, "review_firmware", fake_review)
    return TestClient(main.create_app(settings(max_active_runs=10, rate_limit_per_hour=50, max_firmware_bytes=5000, max_text_bytes=500, **overrides)))


def wait_for(client, run_id):
    for _ in range(100):
        body = client.get(f"/api/runs/{run_id}/review").json()
        if not body["pending"]:
            return body
        time.sleep(0.02)
    raise AssertionError("review never finished")


def test_sanitizes_the_reply(monkeypatch):
    class FakeLLM:
        calls = []

        def __init__(self, settings):
            pass

        async def json(self, system, user, schema, step):
            return ReviewReply(
                summary="s" * 900,
                concerns=[ReviewConcern(title="Might chatter", detail="d", lines=[2, 9999, -1], confidence="high"), ReviewConcern()],
                suggested_fix="add hysteresis",
            )

    monkeypatch.setattr(review, "LLMClient", FakeLLM)
    import asyncio

    out = asyncio.run(review.review_firmware(settings(), FIRMWARE, DeviceSpec()))
    assert out["executed"] is False
    assert out["verdict"] == "issues_found"
    assert len(out["summary"]) == 500
    assert [c["lines"] for c in out["concerns"]] == [[2]]


def test_review_is_off_unless_asked_for(monkeypatch):
    calls = []

    async def fake(cfg, firmware, spec):
        calls.append(firmware)
        return {"concerns": []}

    c = client(monkeypatch, fake)
    run_id = c.post("/api/runs", json=RUN).json()["run_id"]
    assert c.get(f"/api/runs/{run_id}/review").json() == {"review": None, "pending": False, "error": ""}
    assert calls == []


def test_compare_flag_runs_one_review_and_it_is_cached(monkeypatch):
    calls = []

    async def fake(cfg, firmware, spec):
        calls.append(firmware)
        return {"verdict": "issues_found", "concerns": [{"title": "Might chatter"}]}

    c = client(monkeypatch, fake)
    run_id = c.post("/api/runs", json={**RUN, "compare": True}).json()["run_id"]
    body = wait_for(c, run_id)
    assert body["review"]["concerns"][0]["title"] == "Might chatter"
    again = c.post(f"/api/runs/{run_id}/review")
    assert again.status_code == 202 and again.json()["review"] is not None
    assert len(calls) == 1


def test_on_demand_review_and_failure_can_be_retried(monkeypatch):
    outcomes = [review.LLMError("model unreachable"), {"concerns": []}]

    async def fake(cfg, firmware, spec):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    c = client(monkeypatch, fake)
    run_id = c.post("/api/runs", json=RUN).json()["run_id"]
    assert c.post(f"/api/runs/{run_id}/review").status_code == 202
    failed = wait_for(c, run_id)
    assert failed["review"] is None and "unreachable" in failed["error"]
    assert c.post(f"/api/runs/{run_id}/review").status_code == 202
    assert wait_for(c, run_id)["review"] == {"concerns": []}


def test_review_needs_the_passcode_and_a_reviewable_run(monkeypatch):
    async def fake(cfg, firmware, spec):
        return {"concerns": []}

    c = client(monkeypatch, fake, demo_passcode="sesame")
    headers = {"X-Demo-Passcode": "sesame"}
    run_id = c.post("/api/runs", json=RUN, headers=headers).json()["run_id"]
    assert c.post(f"/api/runs/{run_id}/review").status_code == 401
    assert c.post(f"/api/runs/{run_id}/review", headers=headers).status_code == 202
    assert c.post("/api/runs/nope/review", headers=headers).status_code == 404
    hostile = c.post("/api/runs", json={**RUN, "firmware": '#include "/etc/passwd"\nvoid setup(){}\nvoid loop(){}'}, headers=headers).json()
    assert hostile["guard"]["allowed"] is False
    assert c.post(f"/api/runs/{hostile['run_id']}/review", headers=headers).status_code == 409
