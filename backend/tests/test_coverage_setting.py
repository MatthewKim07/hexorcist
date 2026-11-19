"""The spec-coverage switch: off by default, read from COVERAGE, shown by /api/health without touching the agent block."""
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from app.models import OutputFollows
from tests.test_api import settings


def test_coverage_is_off_unless_asked(monkeypatch):
    monkeypatch.delenv("COVERAGE", raising=False)
    assert load_settings().coverage is False
    monkeypatch.setenv("COVERAGE", "1")
    assert load_settings().coverage is True


def test_health_reports_the_switch_outside_the_agent_block():
    off = TestClient(create_app(settings())).get("/api/health").json()
    on = TestClient(create_app(settings(coverage=True))).get("/api/health").json()
    assert off["coverage"] == {"enabled": False} and on["coverage"] == {"enabled": True}
    assert "coverage" not in off["agent"]


def test_an_assertion_has_no_origin_unless_the_coverage_step_set_one():
    a = OutputFollows.model_validate({"type": "output_follows", "pin": "D9", "high_when": {"pin": "A0", "op": ">=", "value": 1}})
    assert a.origin is None and "origin" not in a.model_dump(exclude_none=True)
