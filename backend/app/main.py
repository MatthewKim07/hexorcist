"""HTTP API. Holds the Docker socket and LLM key, so this process is the trust boundary."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from .agent import Pipeline, execute_run
from .checks import CheckSet, read_checks
from .config import Settings, load_settings
from .events import BusRegistry
from .guard import screen_request
from .llm import LLMError
from .models import DeviceSpec, PinSpec
from .presets import PRESETS
from .review import review_firmware
from .sandbox import SandboxRunner
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class RunRequest(BaseModel):
    mode: Literal["break", "build"] = "break"
    title: str = Field(default="", max_length=120)
    firmware: str = ""
    pins: list[dict] = Field(default_factory=list, max_length=20)
    behaviour: str = ""
    description: str = ""
    # Also ask the model for a plain code review (one extra call) to show beside the measured results.
    compare: bool = False
    # Checks from a preview or an example. The run evaluates these instead of reading the spec again.
    checks: Optional[CheckSet] = None


class ChecksRequest(BaseModel):
    firmware: str = ""
    pins: list[dict] = Field(default_factory=list, max_length=20)
    behaviour: str = ""


# Guessing the passcode must cost the guesser something, so failures are limited per address.
PASSCODE_FAILURES_PER_HOUR = 20


class RateLimiter:
    def __init__(self, per_hour: int) -> None:
        self.per_hour = per_hour
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        if self.per_hour <= 0:
            return True
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= self.per_hour:
            return False
        hits.append(now)
        return True


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    cfg = settings or load_settings()
    if os.environ.get("REQUIRE_DEMO_PASSCODE", "") == "1" and not cfg.demo_passcode:
        raise RuntimeError("REQUIRE_DEMO_PASSCODE is set but DEMO_PASSCODE is empty. Refusing to serve a public demo with no passcode.")
    app = FastAPI(title="Hexorcist", version="0.1.0")
    store = Store(cfg.db_path)
    registry = BusRegistry(store)
    runner = SandboxRunner(cfg)
    limiter = RateLimiter(cfg.rate_limit_per_hour)
    guesses = RateLimiter(PASSCODE_FAILURES_PER_HOUR)
    review_limiter = RateLimiter(cfg.rate_limit_per_hour)
    checks_limiter = RateLimiter(cfg.rate_limit_per_hour)
    tasks: set[asyncio.Task] = set()
    reviews_pending: set[str] = set()
    review_errors: dict[str, str] = {}
    trust_proxy = os.environ.get("TRUST_PROXY", "") == "1"
    # Only when every request arrives through a Cloudflare tunnel, which sets this header itself.
    trust_cloudflare = os.environ.get("TRUST_CLOUDFLARE", "") == "1"

    def client_ip(request: Request) -> str:
        if trust_cloudflare and request.headers.get("cf-connecting-ip"):
            return request.headers["cf-connecting-ip"].strip()
        if trust_proxy and request.headers.get("x-real-ip"):
            return request.headers["x-real-ip"]
        return request.client.host if request.client else "unknown"

    def check_passcode(request: Request, supplied: Optional[str]) -> None:
        if cfg.demo_passcode and not hmac.compare_digest((supplied or "").encode(), cfg.demo_passcode.encode()):
            if not guesses.allow(client_ip(request)):
                raise HTTPException(429, "Too many wrong passcodes from this address. Try again later.")
            raise HTTPException(401, "A valid demo passcode is required.")

    def start_review(run_id: str, firmware: str, spec: DeviceSpec) -> None:
        """One LLM call in the background. Only successes are stored, so a failed review can be retried."""
        if run_id in reviews_pending:
            return
        reviews_pending.add(run_id)
        review_errors.pop(run_id, None)

        async def work() -> None:
            try:
                review = await review_firmware(cfg, firmware, spec)
                await asyncio.to_thread(store.save_review, run_id, review)
            except LLMError as exc:
                review_errors[run_id] = str(exc)[:300]
            except Exception as exc:  # noqa: BLE001 - the review is optional, so it must never take anything else down
                logging.getLogger("hexorcist.review").error("review of run %s failed: %r", run_id, exc)
                review_errors[run_id] = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                reviews_pending.discard(run_id)

        task = asyncio.create_task(work())
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @app.get("/api/health")
    async def health() -> dict:
        sandbox = await asyncio.to_thread(runner.health)
        return {
            "ok": sandbox["docker"] and sandbox["image"],
            "sandbox": sandbox,
            "llm_configured": cfg.llm_configured,
            "llm_model": cfg.llm_model,
            "llm_base_url": cfg.llm_base_url,
            "passcode_required": bool(cfg.demo_passcode),
            "limits": {
                "max_firmware_bytes": cfg.max_firmware_bytes,
                "max_text_bytes": cfg.max_text_bytes,
                "rate_limit_per_hour": cfg.rate_limit_per_hour,
                "max_active_runs": cfg.max_active_runs,
            },
        }

    @app.get("/api/presets")
    async def presets() -> list[dict]:
        return PRESETS

    def checked_upload(firmware: str, texts: dict[str, str], raw_pins: list[dict]) -> list[PinSpec]:
        if len(firmware.encode()) > cfg.max_firmware_bytes:
            raise HTTPException(413, f"Firmware is larger than {cfg.max_firmware_bytes} bytes.")
        for name, text in texts.items():
            if len(text.encode()) > cfg.max_text_bytes:
                raise HTTPException(413, f"The {name} text is longer than {cfg.max_text_bytes} bytes.")
        try:
            return [PinSpec(**p) for p in raw_pins]
        except (ValidationError, TypeError) as exc:
            raise HTTPException(422, f"Invalid pin map: {exc}") from exc

    @app.post("/api/checks")
    async def preview_checks(body: ChecksRequest, request: Request, x_demo_passcode: Optional[str] = Header(default=None)) -> dict:
        """The run's UNDERSTAND step on its own: one LLM call that turns the behaviour text into the checks a run would evaluate."""
        check_passcode(request, x_demo_passcode)
        pins = checked_upload(body.firmware, {"behaviour": body.behaviour}, body.pins)
        if not body.behaviour.strip():
            raise HTTPException(422, "Describe the intended behaviour, so there is something to read checks from.")
        if not cfg.llm_configured:
            raise HTTPException(503, "The LLM is not configured.")
        spec = DeviceSpec(pins=pins, behaviour=body.behaviour)
        verdict = await asyncio.to_thread(screen_request, body.firmware, "\n".join([body.behaviour] + [f"{p.role} {p.scale}" for p in pins]))
        if not verdict["allowed"]:
            raise HTTPException(422, "The input guard flagged this upload, so the model was not asked. Run it to see the guard's reasons and the containment report.")
        if not checks_limiter.allow(client_ip(request)):
            raise HTTPException(429, "Rate limit reached for check previews from this address. Try again later.")
        try:
            return await read_checks(cfg, body.firmware, spec)
        except LLMError as exc:
            raise HTTPException(502, f"The model could not be reached: {str(exc)[:200]}") from exc

    @app.post("/api/runs", status_code=201)
    async def create_run(body: RunRequest, request: Request, x_demo_passcode: Optional[str] = Header(default=None)) -> dict:
        check_passcode(request, x_demo_passcode)
        pins = checked_upload(body.firmware, {"behaviour": body.behaviour, "description": body.description}, body.pins)
        if body.mode == "break":
            if not body.firmware.strip():
                raise HTTPException(422, "Paste a sketch to attack.")
            if not body.behaviour.strip():
                raise HTTPException(422, "Describe the intended behaviour, so there is a spec to hold the firmware to.")
        elif not body.description.strip():
            raise HTTPException(422, "Describe the device you want built.")
        if registry.active_count() >= cfg.max_active_runs:
            raise HTTPException(429, "Too many runs in progress. Try again shortly.")
        if not limiter.allow(client_ip(request)):
            raise HTTPException(429, "Rate limit reached for this address. Try again later.")

        spec = DeviceSpec(pins=pins, behaviour=body.behaviour)
        spec_text = "\n".join([body.behaviour, body.description, body.title] + [f"{p.role} {p.scale}" for p in pins])
        # The classifier is plain Python, and a large upload takes a moment, so keep it off the event loop.
        verdict = await asyncio.to_thread(screen_request, body.firmware, spec_text)

        run_id = uuid.uuid4().hex[:12]
        title = body.title or (body.description[:60] if body.mode == "build" else _sketch_title(body.firmware))
        store.create_run(run_id, body.mode, title, body.firmware, spec.model_dump(), dict(verdict))
        bus = registry.create(run_id)
        await bus.emit("guard", guard=dict(verdict))
        if body.compare and body.mode == "break" and verdict["allowed"] and cfg.llm_configured and review_limiter.allow(client_ip(request)):
            start_review(run_id, body.firmware, spec)

        pipeline = Pipeline(run_id, cfg, runner, store, bus)
        task = asyncio.create_task(execute_run(pipeline, body.mode, body.firmware, spec, body.description, dict(verdict), body.checks if body.mode == "break" else None))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return {"run_id": run_id, "guard": verdict}

    @app.get("/api/runs")
    async def list_runs() -> list[dict]:
        return await asyncio.to_thread(store.list_runs)

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        run = await asyncio.to_thread(store.get_run, run_id)
        if run is None:
            raise HTTPException(404, "No such run.")
        return run

    @app.get("/api/runs/{run_id}/review")
    async def get_review(run_id: str) -> dict:
        if await asyncio.to_thread(store.get_run, run_id) is None:
            raise HTTPException(404, "No such run.")
        review = await asyncio.to_thread(store.get_review, run_id)
        return {"review": review, "pending": run_id in reviews_pending, "error": review_errors.get(run_id, "")}

    @app.post("/api/runs/{run_id}/review", status_code=202)
    async def create_review(run_id: str, request: Request, x_demo_passcode: Optional[str] = Header(default=None)) -> dict:
        """Ask the model to review the code without running it. Cached, so asking again costs nothing."""
        check_passcode(request, x_demo_passcode)
        run = await asyncio.to_thread(store.get_run, run_id)
        if run is None:
            raise HTTPException(404, "No such run.")
        if run["mode"] != "break" or not run["firmware"].strip() or not run["guard"].get("allowed", False):
            raise HTTPException(409, "Only an accepted Break run has a sketch to review.")
        if not cfg.llm_configured:
            raise HTTPException(503, "The LLM is not configured.")
        existing = await asyncio.to_thread(store.get_review, run_id)
        if existing is None and run_id not in reviews_pending:
            if not review_limiter.allow(client_ip(request)):
                raise HTTPException(429, "Rate limit reached for reviews from this address. Try again later.")
            start_review(run_id, run["firmware"], DeviceSpec(**run["spec"]))
        return {"review": existing, "pending": existing is None, "error": ""}

    @app.get("/api/runs/{run_id}/traces/{iteration}/{scenario_id}")
    async def get_trace(run_id: str, iteration: int, scenario_id: str) -> dict:
        trace = await asyncio.to_thread(store.get_trace, run_id, iteration, scenario_id)
        if trace is None:
            raise HTTPException(404, "No trace for that run, iteration and scenario.")
        return trace

    @app.get("/api/runs/{run_id}/events")
    async def stream_events(run_id: str, request: Request, after: int = 0, last_event_id: Optional[str] = Header(default=None)) -> StreamingResponse:
        if await asyncio.to_thread(store.get_run, run_id) is None:
            raise HTTPException(404, "No such run.")
        start = after
        if last_event_id and last_event_id.isdigit():
            start = max(start, int(last_event_id))

        async def generate():
            async for event in registry.subscribe(run_id, start):
                if await request.is_disconnected():
                    return
                if not event:
                    yield ": keep-alive\n\n"
                    continue
                yield f"id: {event['seq']}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
            yield "event: end\ndata: {}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs/{run_id}/events.json")
    async def poll_events(run_id: str, after: int = 0) -> dict:
        """Plain JSON version of the event stream, for networks that buffer server-sent events."""
        if await asyncio.to_thread(store.get_run, run_id) is None:
            raise HTTPException(404, "No such run.")
        bus = registry._buses.get(run_id)
        closed = bus is None or bus.closed
        events = await asyncio.to_thread(store.events, run_id, after)
        return {"events": events, "done": closed}

    app.state.store = store
    return app


def _sketch_title(firmware: str) -> str:
    for line in firmware.splitlines():
        text = line.strip().lstrip("/").strip()
        if text:
            return text[:60]
    return "Untitled sketch"


app = create_app()
