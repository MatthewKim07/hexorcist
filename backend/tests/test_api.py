"""API guard rails. These requests are all rejected before any sandbox or LLM work starts."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import PASSCODE_FAILURES_PER_HOUR, RateLimiter, create_app


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


def test_required_passcode_refuses_to_start_without_one(monkeypatch):
    monkeypatch.setenv("REQUIRE_DEMO_PASSCODE", "1")
    try:
        create_app(settings(demo_passcode=""))
    except RuntimeError as exc:
        assert "DEMO_PASSCODE" in str(exc)
    else:
        raise AssertionError("started with no passcode")
    create_app(settings(demo_passcode="sesame"))


def test_passcode_guesses_are_limited_per_address():
    client = TestClient(create_app(settings(demo_passcode="sesame")))
    codes = [client.post("/api/runs", json=GOOD, headers={"X-Demo-Passcode": "wrong"}).status_code for _ in range(PASSCODE_FAILURES_PER_HOUR + 1)]
    assert codes[:-1] == [401] * PASSCODE_FAILURES_PER_HOUR
    assert codes[-1] == 429


def test_passcode_compares_non_ascii_without_crashing():
    client = TestClient(create_app(settings(demo_passcode="sésame")))
    assert client.post("/api/runs", json=GOOD, headers={"X-Demo-Passcode": "wrong"}).status_code == 401


def test_health_reports_limits_and_no_secrets():
    client = TestClient(create_app(settings(demo_passcode="sesame", llm_api_key="the-key")))
    body = client.get("/api/health")
    assert body.json()["limits"]["rate_limit_per_hour"] == 5
    assert body.json()["passcode_required"] is True
    assert "the-key" not in body.text and "sesame" not in body.text


def test_cloudflare_address_is_used_only_when_trusted(monkeypatch):
    def wrong_codes(client, ip):
        return [client.post("/api/runs", json=GOOD, headers={"X-Demo-Passcode": "wrong", "CF-Connecting-IP": ip}).status_code for _ in range(PASSCODE_FAILURES_PER_HOUR + 1)]

    # Not trusted: the header is ignored, so two visitors share one bucket.
    client = TestClient(create_app(settings(demo_passcode="sesame")))
    assert wrong_codes(client, "203.0.113.1")[-1] == 429
    assert wrong_codes(client, "203.0.113.2")[-1] == 429

    # Trusted: each visitor address has its own bucket.
    monkeypatch.setenv("TRUST_CLOUDFLARE", "1")
    client = TestClient(create_app(settings(demo_passcode="sesame")))
    assert wrong_codes(client, "203.0.113.1")[-1] == 429
    second = wrong_codes(client, "203.0.113.2")
    assert second[:-1] == [401] * PASSCODE_FAILURES_PER_HOUR
    assert second[-1] == 429


def test_events_can_be_polled_as_json():
    app = create_app(settings())
    client = TestClient(app)
    assert client.get("/api/runs/nope/events.json").status_code == 404
    app.state.store.create_run("r1", "break", "t", "void setup(){}", {}, {})
    app.state.store.add_event("r1", 1, {"seq": 1, "type": "step"})
    app.state.store.add_event("r1", 2, {"seq": 2, "type": "done"})
    body = client.get("/api/runs/r1/events.json").json()
    assert [e["seq"] for e in body["events"]] == [1, 2]
    assert body["done"] is True
    assert [e["seq"] for e in client.get("/api/runs/r1/events.json?after=1").json()["events"]] == [2]
