"""API guard rails. These requests are all rejected before any sandbox or LLM work starts."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import RateLimiter, create_app


def settings(**overrides) -> Settings:
    base = dict(
        llm_base_url="http://unused/v1",
        llm_api_key="k",
        llm_model="m",
        demo_passcode="",
        sandbox_image="hexorcist-sandbox:latest",
        db_path=":memory:",
        max_parallel=1,
        compile_timeout_s=60,
        run_timeout_s=30,
        max_firmware_bytes=100,
        max_text_bytes=50,
        rate_limit_per_hour=5,
        max_active_runs=1,
        llm_timeout_s=1,
    )
    base.update(overrides)
    return Settings(**base)


GOOD = {"mode": "break", "firmware": "void setup(){}", "behaviour": "x", "pins": []}


def test_passcode_required():
    client = TestClient(create_app(settings(demo_passcode="sesame")))
    assert client.post("/api/runs", json=GOOD).status_code == 401
    assert client.post("/api/runs", json=GOOD, headers={"X-Demo-Passcode": "wrong"}).status_code == 401


def test_size_limits():
    client = TestClient(create_app(settings()))
    assert client.post("/api/runs", json={**GOOD, "firmware": "x" * 101}).status_code == 413
    assert client.post("/api/runs", json={**GOOD, "behaviour": "x" * 51}).status_code == 413


def test_validation():
    client = TestClient(create_app(settings()))
    assert client.post("/api/runs", json={**GOOD, "firmware": " "}).status_code == 422
    assert client.post("/api/runs", json={**GOOD, "behaviour": ""}).status_code == 422
    assert client.post("/api/runs", json={"mode": "build", "description": ""}).status_code == 422
    assert client.post("/api/runs", json={**GOOD, "pins": [{"pin": "Z9", "type": "analog_input"}]}).status_code == 422


def test_unknown_run_is_404():
    client = TestClient(create_app(settings()))
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/runs/nope/events").status_code == 404


def test_presets_are_served():
    client = TestClient(create_app(settings()))
    assert {p["id"] for p in client.get("/api/presets").json()} == {"thermostat", "button", "logger", "alarm", "containment"}


def test_rate_limiter():
    limiter = RateLimiter(2)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")
