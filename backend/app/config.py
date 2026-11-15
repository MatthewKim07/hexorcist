"""Runtime configuration. Everything comes from the environment, nothing is provider specific."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# For running outside Docker. Real environment variables win, and compose passes env_file itself.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    demo_passcode: str
    sandbox_image: str
    db_path: str
    max_parallel: int
    compile_timeout_s: int
    run_timeout_s: int
    max_firmware_bytes: int
    max_text_bytes: int
    rate_limit_per_hour: int
    max_active_runs: int
    llm_timeout_s: int
    # Clean-room cross-check: an implementation written from the spec alone, used to tell a firmware bug
    # from a check that no correct firmware could pass.
    cross_check: bool = True
    # How many independent clean-room sketches to write (1 or 2). A check is dropped only if every one of them fails it.
    cleanroom_samples: int = 2
    # Stimulus search: bounded variants of each scenario, run on the uploaded firmware. 0 turns it off.
    search_variants: int = 30
    search_seed: int = 1337
    search_budget_s: int = 90

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model and self.llm_base_url)


def load_settings() -> Settings:
    return Settings(
        llm_base_url=os.environ.get("LLM_BASE_URL", "").strip(),
        llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
        llm_model=os.environ.get("LLM_MODEL", "").strip(),
        demo_passcode=os.environ.get("DEMO_PASSCODE", "").strip(),
        sandbox_image=os.environ.get("SANDBOX_IMAGE", "hexorcist-sandbox:latest"),
        db_path=os.environ.get("HEXORCIST_DB", "data/hexorcist.sqlite3"),
        max_parallel=_int("SANDBOX_MAX_PARALLEL", 4),
        compile_timeout_s=_int("SANDBOX_COMPILE_TIMEOUT_S", 60),
        run_timeout_s=_int("SANDBOX_RUN_TIMEOUT_S", 30),
        max_firmware_bytes=_int("MAX_FIRMWARE_BYTES", 64 * 1024),
        max_text_bytes=_int("MAX_TEXT_BYTES", 8 * 1024),
        rate_limit_per_hour=_int("RATE_LIMIT_PER_HOUR", 20),
        max_active_runs=_int("MAX_ACTIVE_RUNS", 3),
        llm_timeout_s=_int("LLM_TIMEOUT_S", 180),
        cross_check=_flag("CLEANROOM", True),
        cleanroom_samples=max(1, min(2, _int("CLEANROOM_SAMPLES", 2))),
        search_variants=max(0, _int("SEARCH_VARIANTS", 30)),
        search_seed=_int("SEARCH_SEED", 1337),
        search_budget_s=max(0, _int("SEARCH_BUDGET_S", 90)),
    )


settings = load_settings()
