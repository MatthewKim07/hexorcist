"""Bench plumbing for the spec-coverage step: run_dev.sh --coverage, the bench override, the health pre-flight and the rows."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.coverage_rows import coverage_row  # noqa: E402

RUN_DEV = ROOT / "bench" / "run_dev.sh"
VENV = ROOT / "backend" / ".venv" / "bin" / "python"
needs_venv = pytest.mark.skipif(not VENV.exists(), reason="needs the backend venv that run_dev.sh uses")


def run_list(*args):
    return subprocess.run(["bash", str(RUN_DEV), "--list", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


@needs_venv
def test_coverage_is_off_in_a_default_listing():
    out = run_list("--cases", "weather_ok")
    assert "coverage: off" in out.stdout and "_coverage" not in out.stdout.splitlines()[0]


@needs_venv
def test_the_coverage_flag_turns_it_on_and_keeps_the_run_apart_from_one_without_it():
    out = run_list("--coverage", "--cases", "weather_ok")
    assert "coverage: ON" in out.stdout and "_coverage" in out.stdout.splitlines()[0]
    both = run_list("--coverage", "--search", "5", "--dir", "practice")
    assert "coverage: ON" in both.stdout and "ON, 5 variants" in both.stdout


def test_the_bench_stack_turns_coverage_off_unless_the_run_asks_for_it():
    compose = (ROOT / "bench" / "docker-compose.bench.yml").read_text()
    assert 'COVERAGE: "${BENCH_COVERAGE:-0}"' in compose


def test_the_health_preflight_refuses_a_stack_that_disagrees_with_the_flag():
    script = RUN_DEV.read_text()
    assert 'export BENCH_COVERAGE="$COVERAGE_ON"' in script
    assert 'WANT_COVERAGE="$COVERAGE_ON"' in script
    assert "the spec-coverage step must be" in script and "does not know the spec-coverage switch" in script


def test_a_row_without_the_step_has_no_coverage_record():
    assert coverage_row(None) is None and coverage_row({}) is None


def test_a_row_keeps_what_the_step_did_but_not_the_bullet_detail():
    row = coverage_row(
        {
            "enabled": True,
            "bullets": [{"bullet": "a b c", "covered": True, "covered_by": ["a1"]}, {"bullet": "d e f", "covered": False, "covered_by": []}],
            "uncovered": ["d e f"],
            "called": True,
            "proposed": 2,
            "added": ["a3"],
            "rejected": [{"reason": "x", "quote": "y"}],
            "dropped": [],
            "displaced": [],
            "error": "",
        }
    )
    assert row == {"uncovered": ["d e f"], "bullets": 2, "called": True, "proposed": 2, "added": ["a3"], "rejected": [{"reason": "x", "quote": "y"}], "dropped": [], "displaced": [], "error": ""}
