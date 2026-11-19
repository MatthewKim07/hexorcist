"""The coverage step through the real client: JSON text in, parsed and repaired exactly as in production.

The earlier tests handed `_cover_spec` ready-made dicts, so a reply that lacks the "spec_quote" key (which is what the
real runs returned) never reached the parser. These tests script only the model's text and use the real LLMClient.json.
"""
import asyncio
import json

from app import coverage, prompts
from app.agent import Pipeline, normalize_assertions
from app.llm import LLMCall, LLMClient
from app.models import DeviceSpec, PinSpec
from tests.test_api import settings
from tests.test_cross_check import RoomRunner
from tests.test_fix_loop import NullBus, NullStore

SPEC_TEXT = "- Relay on D9 follows the sensor on A0.\n- A status line is printed every 1000 ms.\n- Relay on D9 must not chatter.\n"
SPEC = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output"), PinSpec(pin="A0", type="analog_input")], behaviour=SPEC_TEXT)
FIRST = [{"type": "output_follows", "pin": "D9", "high_when": {"pin": "A0", "op": ">=", "value": 30}, "spec_quote": "Relay on D9 follows the sensor on A0"}]
CHECK = {"type": "serial_period", "pattern": "^status", "period_ms": 1000, "tolerance_ms": 100, "description": "Status line", "spec_quote": "A status line is printed every 1000 ms"}


class TextClient(LLMClient):
    """The real LLMClient.json (parse, validate, one repair); only the model's text is scripted."""

    def __init__(self, replies):
        super().__init__(settings(llm_base_url="http://x/v1", llm_api_key="k", llm_model="m"))
        self.replies = list(replies)
        self.sent: list[list[dict]] = []

    async def _complete(self, messages, step, json_mode, temperature=None, seed=None):
        self.sent.append([dict(m) for m in messages])
        self.calls.append(LLMCall(step=step, duration_ms=1, prompt_tokens=10, completion_tokens=5))
        return self.replies.pop(0)


def cover(replies):
    pipeline = Pipeline("r", settings(max_parallel=2, coverage=True), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = TextClient(replies)
    assertions, _ = normalize_assertions(FIRST, SPEC, ground=True)
    merged = asyncio.run(pipeline._cover_spec("void setup() {}\nvoid loop() {}\n", SPEC, assertions))
    return pipeline, merged


def reply(*items, fenced=False):
    text = json.dumps({"assertions": list(items)})
    return f"```json\n{text}\n```" if fenced else text


def test_a_reply_in_the_documented_shape_is_parsed_vetted_and_added():
    pipeline, merged = cover([reply(CHECK)])
    cov = pipeline.coverage
    assert cov["proposed"] == 1 and cov["rejected"] == [] and len(cov["added"]) == 1
    added = next(a for a in merged if a.id == cov["added"][0])
    assert added.type == "serial_period" and added.origin == "coverage" and added.spec_quote == CHECK["spec_quote"]
    # The first-pass check carries an int default (min_trigger_ms) that becomes a float on re-parse: it must not look new.
    assert [x.origin for x in merged if x.type == "output_follows"] == [None]


def test_a_fenced_reply_goes_through_the_same_parser():
    pipeline, merged = cover([reply(CHECK, fenced=True)])
    assert len(pipeline.coverage["added"]) == 1


def test_a_reply_without_the_spec_quote_key_is_sent_back_once_and_the_repair_is_used():
    bare = {k: v for k, v in CHECK.items() if k != "spec_quote"}
    pipeline, merged = cover([reply(bare), reply(CHECK)])
    client = pipeline.llm
    assert len(client.sent) == 2 and client.calls[-1].repaired is True
    told = client.sent[1][-1]["content"]
    assert 'spec_quote' in told and "its keys are" in told  # the repair message names the key and what was sent
    assert len(pipeline.coverage["added"]) == 1 and pipeline.coverage["rejected"] == []


def test_a_reply_that_names_the_quote_differently_is_not_guessed_at():
    renamed = {k if k != "spec_quote" else "quote": v for k, v in CHECK.items()}
    pipeline, merged = cover([reply(renamed), reply(renamed)])
    cov = pipeline.coverage
    assert cov["added"] == [] and "spec_quote" in cov["error"]
    assert [a.type for a in merged] == ["output_follows", "no_crash"]


def test_an_empty_quote_is_never_accepted():
    pipeline, merged = cover([reply({**CHECK, "spec_quote": ""}), reply({**CHECK, "spec_quote": "  "})])
    assert pipeline.coverage["added"] == [] and pipeline.coverage["error"]


def test_a_reply_with_no_checks_is_a_normal_empty_answer_and_costs_one_call():
    pipeline, merged = cover([reply()])
    assert len(pipeline.llm.sent) == 1 and pipeline.coverage["proposed"] == 0 and pipeline.coverage["error"] == ""


def test_a_crash_check_needs_no_quote():
    assert prompts.CoverageReply.model_validate({"assertions": [{"type": "no_crash"}]}).assertions == [{"type": "no_crash"}]


def test_a_quote_from_another_bullet_is_rejected_with_enough_detail_to_debug_it():
    wrong = {**CHECK, "spec_quote": "Relay on D9 follows the sensor on A0", "description": "x" * 300, "origin": "coverage"}
    pipeline, merged = cover([reply(wrong)])
    rej = pipeline.coverage["rejected"]
    assert len(rej) == 1 and rej[0]["reason"] == "its spec_quote is not inside an uncovered bullet"
    assert rej[0]["quote"] == "Relay on D9 follows the sensor on A0" and rej[0]["type"] == "serial_period"
    assert len(rej[0]["title"]) <= 80 and rej[0]["title"].endswith("…")
    assert "spec_quote" in rej[0]["keys"] and "origin" not in rej[0]["keys"]


def test_a_rejection_records_an_empty_quote_as_such_not_as_a_bullet_mismatch():
    kept, rejected = coverage.vet([{"type": "serial_period", "description": "d", "spec_quote": ""}], ["A status line is printed every 1000 ms."])
    assert kept == [] and rejected[0]["reason"] == "it has no spec_quote" and rejected[0]["keys"] == ["description", "spec_quote", "type"]


def test_the_prompt_shows_the_spec_quote_key_in_an_example_assertion():
    assert '"spec_quote":"a heartbeat line every 500 ms"' in prompts.COVERAGE_SYSTEM
