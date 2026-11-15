"""The clock fast-forward as the backend sees it. The harness side is proved in the sandbox by scripts/verify_sandbox."""
import pytest
from pydantic import ValidationError

from app.models import Scenario


def test_a_scenario_starts_at_power_on_unless_told_otherwise():
    s = Scenario(name="s")
    assert s.start_millis == 0
    assert s.harness_json()["start_millis"] == 0


def test_a_scenario_can_start_just_before_the_millis_rollover_or_hours_in():
    assert Scenario(name="s", start_millis=2**32 - 5000).harness_json()["start_millis"] == 4294962296
    assert Scenario(name="s", start_millis=3 * 3600 * 1000).start_millis == 10_800_000


def test_the_start_must_fit_the_32_bit_counter():
    for bad in (-1, 2**32, 2**40):
        with pytest.raises(ValidationError):
            Scenario(name="s", start_millis=bad)


def test_a_scenario_from_a_model_may_leave_the_start_out():
    assert Scenario.model_validate({"name": "s", "duration_ms": 1000}).start_millis == 0
