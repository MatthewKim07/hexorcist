"""Device spec, scenario and assertion schemas shared by the whole backend."""
from __future__ import annotations

import re
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

ANALOG_PINS = {f"A{i}" for i in range(6)}
DIGITAL_PINS = {f"D{i}" for i in range(14)}
ALL_PINS = ANALOG_PINS | DIGITAL_PINS

MAX_SCENARIO_MS = 15000
MAX_POINTS = 64


def normalize_pin(value: str) -> str:
    """Accept '9', 'd9', 'pin 9', 'A0' and return the canonical 'D9' or 'A0'."""
    text = str(value).strip().upper().replace("PIN", "").strip()
    if text.isdigit():
        text = f"D{text}"
    if text not in ALL_PINS:
        raise ValueError(f"unknown Arduino Uno pin: {value!r}")
    return text


Pin = Annotated[str, Field(description="Arduino Uno pin such as D9 or A0")]


class PinSpec(BaseModel):
    pin: str
    role: str = ""
    type: Literal["analog_input", "digital_input", "digital_output", "pwm_output"]
    scale: str = ""
    active_low: bool = False

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)

    def parsed_scale(self) -> tuple[float, float, str]:
        """Return (mv_per_unit, offset_mv, unit) from text like '10 mV/°C + 500 mV'."""
        match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*mV\s*/\s*([^\s,;+]+)", self.scale, re.IGNORECASE)
        if not match:
            return (1.0, 0.0, "mV")
        offset = re.search(r"(?:offset|\+)\s*([-+]?\d+(?:\.\d+)?)\s*mV", self.scale, re.IGNORECASE)
        return (float(match.group(1)) or 1.0, float(offset.group(1)) if offset else 0.0, match.group(2))


class DeviceSpec(BaseModel):
    board: Literal["uno"] = "uno"
    pins: list[PinSpec] = Field(default_factory=list)
    behaviour: str = ""

    def pin(self, name: str) -> Optional[PinSpec]:
        for p in self.pins:
            if p.pin == name:
                return p
        return None

    def inputs(self) -> list[PinSpec]:
        return [p for p in self.pins if p.type in ("analog_input", "digital_input")]

    def outputs(self) -> list[PinSpec]:
        return [p for p in self.pins if p.type in ("digital_output", "pwm_output")]

    def to_mv(self, pin_name: str, physical: float) -> float:
        spec = self.pin(pin_name)
        if spec is None:
            return physical
        mv_per_unit, offset_mv, _ = spec.parsed_scale()
        return physical * mv_per_unit + offset_mv

    def to_physical(self, pin_name: str, mv: float) -> float:
        spec = self.pin(pin_name)
        if spec is None:
            return mv
        mv_per_unit, offset_mv, _ = spec.parsed_scale()
        return (mv - offset_mv) / mv_per_unit


# ---------------------------------------------------------------- scenarios


class AnalogPoint(BaseModel):
    t_ms: float = Field(ge=0)
    mv: float


class Spike(BaseModel):
    t_ms: float = Field(ge=0)
    width_ms: float = Field(default=5, gt=0, le=5000)
    mv: float


class AnalogInput(BaseModel):
    pin: str
    segments: list[AnalogPoint] = Field(min_length=1, max_length=MAX_POINTS)
    noise_mv: float = Field(default=0, ge=0, le=2500)
    spikes: list[Spike] = Field(default_factory=list, max_length=MAX_POINTS)

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        pin = normalize_pin(v)
        if pin not in ANALOG_PINS:
            raise ValueError(f"analog inputs must use A0-A5, got {v!r}")
        return pin


class DigitalEvent(BaseModel):
    t_ms: float = Field(ge=0)
    value: int = Field(ge=0, le=1)
    bounce_ms: float = Field(default=0, ge=0, le=200)
    bounce_count: int = Field(default=0, ge=0, le=32)


class DigitalInput(BaseModel):
    pin: str
    initial: int = Field(default=0, ge=0, le=1)
    events: list[DigitalEvent] = Field(default_factory=list, max_length=256)

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)


class FloatingWindow(BaseModel):
    pin: str
    from_ms: float = Field(default=0, ge=0)
    to_ms: float = Field(default=1e9, ge=0)

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)


class Scenario(BaseModel):
    id: str = ""
    name: str
    hypothesis: str = ""
    source: Literal["builtin", "llm"] = "llm"
    seed: int = Field(default=1, ge=0, le=2**31)
    duration_ms: float = Field(default=8000, gt=0, le=MAX_SCENARIO_MS)
    analog: list[AnalogInput] = Field(default_factory=list)
    digital: list[DigitalInput] = Field(default_factory=list)
    floating: list[FloatingWindow] = Field(default_factory=list)

    def harness_json(self) -> dict:
        """The subset of fields hexharness reads."""
        return {
            "seed": self.seed,
            "duration_ms": self.duration_ms,
            "analog": [a.model_dump() for a in self.analog],
            "digital": [d.model_dump() for d in self.digital],
            "floating": [f.model_dump() for f in self.floating],
        }


# --------------------------------------------------------------- assertions


class Condition(BaseModel):
    """A condition on an input pin. `value` is in physical units of the pin's scale."""

    pin: str
    op: Literal[">", ">=", "<", "<=", "=="]
    value: float

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)

    def holds(self, x: float) -> bool:
        if self.op == ">":
            return x > self.value
        if self.op == ">=":
            return x >= self.value
        if self.op == "<":
            return x < self.value
        if self.op == "<=":
            return x <= self.value
        return abs(x - self.value) < 1e-6


class _AssertionBase(BaseModel):
    id: str = ""
    description: str = ""


class OutputFollows(_AssertionBase):
    type: Literal["output_follows"] = "output_follows"
    pin: str
    high_when: Optional[Condition] = None
    low_when: Optional[Condition] = None
    within_ms: float = Field(default=500, gt=0)
    # level: output must hold the state while the condition holds.
    # edge: output must reach HIGH at some point after the condition starts (latching alarms).
    mode: Literal["level", "edge"] = "level"

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)


class MaxToggles(_AssertionBase):
    type: Literal["max_toggles"] = "max_toggles"
    pin: str
    max_toggles: int = Field(ge=0)
    window_ms: float = Field(gt=0)

    @field_validator("pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)


class TogglePerPress(_AssertionBase):
    """Each settled press of an input must toggle the output exactly once."""

    type: Literal["toggle_per_press"] = "toggle_per_press"
    input_pin: str
    output_pin: str
    active_level: int = Field(default=0, ge=0, le=1)
    settle_ms: float = Field(default=50, gt=0)
    within_ms: float = Field(default=200, gt=0)

    @field_validator("input_pin", "output_pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)


class SerialPeriod(_AssertionBase):
    type: Literal["serial_period"] = "serial_period"
    pattern: str
    period_ms: float = Field(gt=0)
    tolerance_ms: float = Field(ge=0)


class SerialValueMatches(_AssertionBase):
    type: Literal["serial_value_matches"] = "serial_value_matches"
    pattern: str = Field(description="Regex whose first capture group is the printed number")
    input_pin: str
    tolerance: float = Field(gt=0, description="Allowed error in physical units")
    max_lag_ms: float = Field(default=300, ge=0)

    @field_validator("input_pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)


class SafeStateOnFault(_AssertionBase):
    type: Literal["safe_state_on_fault"] = "safe_state_on_fault"
    fault_when: Optional[Condition] = None
    floating_pin: Optional[str] = None
    output_pin: str
    safe_value: int = Field(ge=0, le=1)
    within_ms: float = Field(default=500, gt=0)

    @field_validator("output_pin")
    @classmethod
    def _pin(cls, v: str) -> str:
        return normalize_pin(v)

    @field_validator("floating_pin")
    @classmethod
    def _fpin(cls, v: Optional[str]) -> Optional[str]:
        return normalize_pin(v) if v else v


class Responsive(_AssertionBase):
    type: Literal["responsive"] = "responsive"
    max_gap_ms: float = Field(gt=0)
    start_ms: float = Field(default=0, ge=0)


class NoCrash(_AssertionBase):
    type: Literal["no_crash"] = "no_crash"


Assertion = Annotated[
    Union[
        OutputFollows,
        MaxToggles,
        TogglePerPress,
        SerialPeriod,
        SerialValueMatches,
        SafeStateOnFault,
        Responsive,
        NoCrash,
    ],
    Field(discriminator="type"),
]


class Violation(BaseModel):
    t_start: float
    t_end: float
    detail: str = ""


class AssertionResult(BaseModel):
    assertion_id: str
    scenario_id: str
    type: str
    status: Literal["pass", "fail", "not_exercised"]
    evidence: str = ""
    metrics: dict = Field(default_factory=dict)
    violations: list[Violation] = Field(default_factory=list)
