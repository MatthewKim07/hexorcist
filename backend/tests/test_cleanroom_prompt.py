"""The clean-room prompt makes each room list the spec's facts, and say how the code uses them, before it writes code."""
import asyncio
import re

from app import prompts
from app.agent import Pipeline
from app.models import DeviceSpec, PinSpec
from tests.test_api import settings
from tests.test_cross_check import CLEAN_OK, RoomLLM, RoomRunner
from tests.test_fix_loop import NullBus, NullStore, ORIGINAL, PERSIST_FIXED, SPEC_TEXT

SYSTEM = prompts.CLEANROOM_SYSTEM


def test_the_prompt_asks_for_a_spec_facts_list_before_the_code():
    assert "// SPEC FACTS" in SYSTEM
    assert SYSTEM.index("// SPEC FACTS") < SYSTEM.index("Rules:")
    assert "how the code uses it" in SYSTEM
    assert "starting with the SPEC FACTS comment block" in SYSTEM


def test_the_list_covers_numbers_units_scales_ranges_timings_pin_roles_and_peripherals():
    for word in ("number with its unit", "range", "sensor scale", "timing", "pin and its role", "peripheral"):
        assert word in SYSTEM, word


def test_the_list_says_how_adc_counts_become_the_specs_unit_and_that_serial_needs_setup():
    assert "0 to 1023 for 0 to 5000 mV" in SYSTEM
    assert "never in counts" in SYSTEM
    assert "Serial.begin(9600)" in SYSTEM and "INPUT_PULLUP" in SYSTEM


def test_the_room_checks_its_code_against_the_list_before_finishing():
    assert "a fact that no line of code uses is a missing requirement" in SYSTEM


def test_the_step_is_generic_with_no_case_names_or_case_text():
    lowered = SYSTEM.lower()
    for word in ("silo", "glue", "solenoid", "level", "weather", "nav_beacon", "tank", "mixer", "4200", "859", "2500"):
        assert word not in lowered, word
    assert not re.search(r"\b[a-z]+_[a-z]+_[a-z]+\b", SYSTEM)  # no snake_case case ids


def test_the_old_rules_are_still_there():
    for rule in ("exact numbers", "active LOW", "never block in delay()", "Allman brace style", "Never reference host files"):
        assert rule in SYSTEM, rule


def test_the_untrusted_spec_warning_is_kept():
    assert prompts.UNTRUSTED in SYSTEM


class SeeingLLM(RoomLLM):
    """Scripted model that keeps the system prompt every clean room was given."""

    def __init__(self, patches):
        super().__init__(patches, [[CLEAN_OK], [CLEAN_OK]])
        self.room_system: dict[str, str] = {}

    async def code(self, system, user, step, temperature=None, seed=None):
        if step.startswith("cleanroom"):
            self.room_system[step] = system
        return await super().code(system, user, step, temperature, seed)


def test_both_rooms_are_sent_the_step_in_a_real_run():
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = SeeingLLM([PERSIST_FIXED])
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour=SPEC_TEXT)
    asyncio.run(pipeline.run_break(ORIGINAL, spec))
    assert set(pipeline.llm.room_system) == {"cleanroom1", "cleanroom2"}
    for system in pipeline.llm.room_system.values():
        assert system == SYSTEM and "// SPEC FACTS" in system


def test_the_user_message_still_carries_only_the_spec_and_pin_map():
    spec = DeviceSpec(pins=[PinSpec(pin="A2", type="analog_input", scale="1 mV/mm")], behaviour="- Probe on A2.")
    user = prompts.cleanroom_user(spec)
    assert "1 mV/mm" in user and "SPEC FACTS" not in user
