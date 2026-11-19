"""Spec coverage, the plain part: which bullets are uncovered, and which proposed checks are kept."""
from app import coverage, prompts
from app.coverage import MAX_CHECKS_PER_BULLET, quote_inside, split_bullets, uncovered, vet
from app.models import DeviceSpec, NoCrash, OutputFollows, PinSpec

SPEC = """- Lamp on D8 turns on when the sensor on A0 reads at least 30 units.
- Sensor on A0 has a scale of 10 mV per unit.
- Print a status line every 1000 ms.
- Ok.
"""


def follows(quote, aid="a1"):
    return OutputFollows.model_validate(
        {"type": "output_follows", "pin": "D8", "high_when": {"pin": "A0", "op": ">=", "value": 30}, "id": aid, "spec_quote": quote}
    )


def test_a_bullet_is_covered_when_an_assertion_quote_falls_inside_it():
    parts = split_bullets(SPEC, [follows("turns on when the sensor on A0 reads at least 30 units")])
    assert [(p["covered"], p["covered_by"]) for p in parts] == [(True, ["a1"]), (False, []), (False, [])]


def test_the_split_follows_the_spec_text_not_the_assertions():
    parts = split_bullets(SPEC, [])
    assert [p["bullet"] for p in parts] == [
        "Lamp on D8 turns on when the sensor on A0 reads at least 30 units.",
        "Sensor on A0 has a scale of 10 mV per unit.",
        "Print a status line every 1000 ms.",
    ]
    assert uncovered(parts) == [p["bullet"] for p in parts]


def test_a_bullet_too_short_to_quote_is_left_out():
    assert all("Ok" not in p["bullet"] for p in split_bullets(SPEC, []))


def test_a_check_without_a_quote_or_a_crash_check_covers_nothing():
    parts = split_bullets(SPEC, [follows(""), NoCrash(id="a2")])
    assert not any(p["covered"] for p in parts)


def test_a_quote_naming_a_number_the_bullet_lacks_does_not_cover_it():
    assert not quote_inside("reads at least 99 units", "Lamp turns on when the sensor reads at least 30 units.")
    assert quote_inside("reads at least 30 units", "Lamp turns on when the sensor reads at least 30 units.")


def test_a_two_word_quote_must_sit_inside_the_bullet_in_order():
    assert quote_inside("every 1000", "Print a status line every 1000 ms.")
    assert not quote_inside("1000 every", "Print a status line every 1000 ms.")


UNC = ["Print a status line every 1000 ms.", "Lamp goes off within 200 ms of a release."]


def raw(quote, kind="serial_period"):
    return {"type": kind, "pattern": "^s", "period_ms": 1000, "spec_quote": quote}


def test_vet_keeps_checks_quoting_an_uncovered_bullet_and_drops_the_rest():
    kept, rejected = vet([raw("status line every 1000 ms"), raw("a sentence nobody wrote"), {"type": "no_crash"}, "text"], UNC)
    assert [k["spec_quote"] for k in kept] == ["status line every 1000 ms"]
    assert [r["reason"] for r in rejected] == [
        "its spec_quote is not inside an uncovered bullet",
        "a crash check is always present",
        "not an object",
    ]


def test_vet_allows_at_most_two_checks_per_bullet():
    kept, rejected = vet([raw("status line every 1000 ms"), raw("Print a status line"), raw("line every 1000 ms")], UNC)
    assert len(kept) == MAX_CHECKS_PER_BULLET == 2
    assert "more than 2" in rejected[0]["reason"]


def test_vet_gives_each_bullet_its_own_allowance():
    kept, _ = vet([raw("status line every 1000 ms"), raw("Print a status line"), raw("goes off within 200 ms of a release")], UNC)
    assert len(kept) == 3


def test_vet_discards_an_origin_the_model_supplied():
    kept, _ = vet([{**raw("status line every 1000 ms"), "origin": "coverage"}], UNC)
    assert "origin" not in kept[0]


def test_vet_of_nothing_is_nothing():
    assert vet([], UNC) == ([], []) and vet(None, UNC) == ([], [])


def test_the_prompt_lists_the_uncovered_bullets_and_allows_an_empty_answer():
    spec = DeviceSpec(pins=[PinSpec(pin="D8", type="digital_output")], behaviour=SPEC)
    user = prompts.coverage_user("void setup() {}", spec, UNC)
    assert UNC[0] in user and UNC[1] in user and "void setup" in user and SPEC.splitlines()[0].lstrip("- ") in user
    assert "Returning no assertions at all is a normal, correct answer" in prompts.COVERAGE_SYSTEM
    assert "wiring" in prompts.COVERAGE_SYSTEM and "at most two assertions" in prompts.COVERAGE_SYSTEM
    assert prompts.CoverageReply.model_validate({}).assertions == []
