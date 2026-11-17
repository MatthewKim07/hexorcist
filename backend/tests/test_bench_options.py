"""Bench options: a second case directory, its own fingerprint, and run_dev.sh --dir and --search (list mode only)."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench import case_io, freeze_hash  # noqa: E402

RUN_DEV = ROOT / "bench" / "run_dev.sh"
VENV = ROOT / "backend" / ".venv" / "bin" / "python"


@pytest.fixture(autouse=True)
def restore_dir():
    before = case_io.CASES_DIR
    yield
    case_io.CASES_DIR = before


def test_the_practice_directory_has_ten_cases_and_the_frozen_set_forty():
    case_io.use_cases_dir("practice")
    assert len(case_io.list_case_ids()) == 10
    case_io.use_cases_dir("frozen")
    assert len(case_io.list_case_ids()) == 40


def test_a_case_loads_from_whichever_directory_is_in_use():
    case_io.use_cases_dir("practice")
    case = case_io.load_case("orchard_spray_valve")
    assert case.truth and case.checks["scenarios"]
    with pytest.raises(FileNotFoundError):
        case_io.load_case("weather_ok")


def test_a_missing_directory_is_an_error_not_an_empty_set():
    with pytest.raises(SystemExit):
        case_io.use_cases_dir("no/such/directory")


def test_the_practice_set_is_seven_bugs_and_three_decoys_with_a_clock_scenario():
    case_io.use_cases_dir("practice")
    cases = case_io.load_cases()
    assert sum(1 for c in cases if c.is_correct) == 3 and sum(1 for c in cases if not c.is_correct) == 7
    for c in cases:
        if c.is_correct:
            assert c.sketch.strip() == c.reference.strip()
    started_late = [c.id for c in cases if any(s.get("start_millis") for s in c.checks["scenarios"])]
    assert {"orchard_spray_valve", "tank_mixer_cycle", "meadow_sprinkler_valve"} <= set(started_late)


def test_the_two_sets_have_separate_fingerprints_and_the_practice_one_is_recorded():
    frozen, n_frozen = freeze_hash.freeze_hash()
    practice, n_practice = freeze_hash.freeze_hash(freeze_hash.SETS["practice"][0], frozenset({"README.md"}))
    assert frozen != practice and n_frozen == 240 and n_practice > 0
    assert practice in freeze_hash.SETS["practice"][1].read_text()


def run_list(*args):
    return subprocess.run(["bash", str(RUN_DEV), "--list", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


pytestmark_script = pytest.mark.skipif(not VENV.exists(), reason="needs the backend venv that run_dev.sh uses")


@pytestmark_script
def test_run_dev_lists_the_practice_set_with_search_off_by_default():
    out = run_list("--dir", "practice")
    assert out.returncode == 0, out.stderr
    assert "cases  : 10 from practice" in out.stdout and "search : off" in out.stdout
    assert "orchard_spray_valve" in out.stdout


@pytestmark_script
def test_run_dev_search_flag_turns_the_search_on_with_a_default_or_given_count():
    default = run_list("--dir", "practice", "--search")
    given = run_list("--dir", "practice", "--search", "12")
    assert "ON, 30 variants per case, three acceptance gates" in default.stdout
    assert "ON, 12 variants per case" in given.stdout
    assert "_search_" in default.stdout.splitlines()[0]  # a search run never resumes a run without it


@pytestmark_script
def test_run_dev_refuses_nonsense_options():
    assert run_list("--search", "0").returncode == 2
    assert run_list("--search", "500").returncode == 2
    assert run_list("--dir", "practice", "--cases", "weather_ok").returncode == 2
    assert run_list("--dir").returncode == 2


@pytestmark_script
def test_run_dev_without_options_still_lists_the_forty_frozen_cases():
    out = run_list()
    assert "cases  : 40 from frozen" in out.stdout and "search : off" in out.stdout


def test_the_bench_stack_turns_the_search_off_unless_the_run_asks_for_it():
    compose = (ROOT / "bench" / "docker-compose.bench.yml").read_text()
    assert 'SEARCH_VARIANTS: "${BENCH_SEARCH_VARIANTS:-0}"' in compose
