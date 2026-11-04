"""Built-in attack library. Runs on every firmware, whatever the LLM does or does not produce."""
from __future__ import annotations

from typing import Optional

from .models import (
    AnalogInput,
    AnalogPoint,
    Condition,
    DeviceSpec,
    DigitalEvent,
    DigitalInput,
    FloatingWindow,
    OutputFollows,
    PinSpec,
    SafeStateOnFault,
    Scenario,
    Spike,
)

DURATION_MS = 8000.0
VCC_MV = 5000.0


def _clamp(mv: float) -> float:
    return max(0.0, min(VCC_MV, mv))


def _thresholds_mv(pin: str, spec: DeviceSpec, assertions: list) -> tuple[Optional[float], Optional[float]]:
    """Return (high_threshold_mv, low_threshold_mv) that the assertions imply for an input."""
    high: Optional[float] = None
    low: Optional[float] = None
    for a in assertions:
        if isinstance(a, OutputFollows):
            if a.high_when is not None and a.high_when.pin == pin:
                high = spec.to_mv(pin, a.high_when.value)
            if a.low_when is not None and a.low_when.pin == pin:
                low = spec.to_mv(pin, a.low_when.value)
    return high, low


def _fault_mv(pin: str, spec: DeviceSpec, assertions: list) -> list[float]:
    """Voltages just inside each fault region, so fault checks are actually exercised."""
    out: list[float] = []
    for a in assertions:
        if isinstance(a, SafeStateOnFault) and a.fault_when is not None and a.fault_when.pin == pin:
            c: Condition = a.fault_when
            mv = spec.to_mv(pin, c.value)
            out.append(_clamp(mv + 100 if c.op in (">", ">=") else mv - 100))
    return out


def idle_level(p: PinSpec) -> int:
    return 1 if p.active_low else 0


def fill_defaults(scenario: Scenario, spec: DeviceSpec, assertions: list) -> Scenario:
    """Give every input the scenario leaves alone a sensible resting value."""
    analog_pins = {a.pin for a in scenario.analog}
    digital_pins = {d.pin for d in scenario.digital}
    floating_pins = {f.pin for f in scenario.floating}
    for p in spec.inputs():
        if p.pin in floating_pins:
            continue
        if p.type == "analog_input" and p.pin not in analog_pins:
            high, low = _thresholds_mv(p.pin, spec, assertions)
            rest = low if low is not None else (high * 0.8 if high is not None else 2000.0)
            scenario.analog.append(AnalogInput(pin=p.pin, segments=[AnalogPoint(t_ms=0, mv=_clamp(rest))]))
        elif p.type == "digital_input" and p.pin not in digital_pins:
            scenario.digital.append(DigitalInput(pin=p.pin, initial=idle_level(p)))
    return scenario


def _analog_scenarios(p: PinSpec, spec: DeviceSpec, assertions: list, rest: list[PinSpec]) -> list[Scenario]:
    high, low = _thresholds_mv(p.pin, spec, assertions)
    pin = p.pin
    out: list[Scenario] = []

    def add(sid: str, name: str, hypothesis: str, analog: Optional[AnalogInput] = None, floating: Optional[list] = None, seed: int = 11) -> None:
        out.append(
            Scenario(
                id=f"builtin-{sid}-{pin.lower()}",
                name=f"{name} ({pin})",
                hypothesis=hypothesis,
                source="builtin",
                seed=seed,
                duration_ms=DURATION_MS,
                analog=[analog] if analog else [],
                floating=floating or [],
            )
        )

    centre = high if high is not None else (low if low is not None else 2500.0)
    span_low = _clamp(min(centre * 0.6, (low if low is not None else centre) * 0.9))
    span_high = _clamp(centre * 1.4)
    if span_high - span_low < 200:
        span_low, span_high = _clamp(centre - 500), _clamp(centre + 500)

    # Keep noise well inside any hysteresis band, so firmware with real hysteresis stays quiet.
    hover_noise = max(4.0, (high - low) / 5.0) if high is not None and low is not None and high > low else 12.0

    add(
        "ramp",
        "Nominal ramp",
        "A slow, clean rise then fall across the operating range should behave exactly as specified.",
        AnalogInput(pin=pin, segments=[AnalogPoint(t_ms=0, mv=span_low), AnalogPoint(t_ms=3500, mv=span_high), AnalogPoint(t_ms=4500, mv=span_high), AnalogPoint(t_ms=8000, mv=span_low)]),
        seed=11,
    )
    add(
        "hover",
        "Threshold hover with noise",
        "Sensor noise right at the threshold may make the output chatter if there is no hysteresis.",
        AnalogInput(pin=pin, segments=[AnalogPoint(t_ms=0, mv=span_low), AnalogPoint(t_ms=800, mv=centre), AnalogPoint(t_ms=8000, mv=centre)], noise_mv=hover_noise),
        seed=12,
    )
    add(
        "spike",
        "Glitch spike",
        "A few milliseconds of electrical noise should not flip the output if the firmware filters its input.",
        AnalogInput(
            pin=pin,
            segments=[AnalogPoint(t_ms=0, mv=span_low)],
            spikes=[Spike(t_ms=t, width_ms=30, mv=VCC_MV * 0.95) for t in (1000, 2500, 4000, 5500, 7000)],
        ),
        seed=13,
    )
    add(
        "disconnect",
        "Sensor disconnected (0 V)",
        "A broken wire reads as 0 V. Firmware that trusts it will act on a value that is not real.",
        AnalogInput(pin=pin, segments=[AnalogPoint(t_ms=0, mv=span_low), AnalogPoint(t_ms=1999, mv=span_low), AnalogPoint(t_ms=2000, mv=0), AnalogPoint(t_ms=8000, mv=0)]),
        seed=14,
    )
    add(
        "floating",
        "Floating input",
        "An open input wanders at random and may be acted on as if it were a real reading.",
        None,
        floating=[FloatingWindow(pin=pin, from_ms=0, to_ms=DURATION_MS)],
        seed=15,
    )
    add(
        "extremes",
        "Max and min range",
        "Rail-to-rail readings can overflow conversions or hit unhandled branches.",
        AnalogInput(pin=pin, segments=[AnalogPoint(t_ms=0, mv=VCC_MV), AnalogPoint(t_ms=3900, mv=VCC_MV), AnalogPoint(t_ms=4000, mv=0), AnalogPoint(t_ms=8000, mv=0)]),
        seed=16,
    )

    # Stay inside the hysteresis band when there is one, so correct firmware has no reason to toggle.
    if high is not None and low is not None and high > low:
        amp = (high - low) * 0.4
        mid = high
        desc = "Fast swings around the upper threshold, staying inside the hysteresis band, should not make the output follow every swing."
    else:
        amp = 100.0
        mid = centre
        desc = "Fast swings around the threshold may drag the output along with every cycle."
    points = [AnalogPoint(t_ms=0, mv=_clamp(span_low)), AnalogPoint(t_ms=500, mv=_clamp(mid))]
    t = 600.0
    up = True
    while t < DURATION_MS and len(points) < 60:
        points.append(AnalogPoint(t_ms=t, mv=_clamp(mid + (amp if up else -amp))))
        up = not up
        t += 150.0
    add("oscillation", "Rapid oscillation", desc, AnalogInput(pin=pin, segments=points), seed=17)

    for i, fault in enumerate(_fault_mv(pin, spec, assertions)):
        if fault > 100.0:
            add(
                f"fault{i}",
                f"Out-of-range hold at {fault:.0f} mV",
                "Holding the reading inside the specified fault region must drive the safe state.",
                AnalogInput(pin=pin, segments=[AnalogPoint(t_ms=0, mv=_clamp(centre * 0.8)), AnalogPoint(t_ms=1999, mv=_clamp(centre * 0.8)), AnalogPoint(t_ms=2000, mv=fault), AnalogPoint(t_ms=8000, mv=fault)]),
                seed=18 + i,
            )
    return out


def _button_scenarios(p: PinSpec) -> list[Scenario]:
    pin = p.pin
    idle = idle_level(p)
    active = 1 - idle
    out: list[Scenario] = []

    press_times = [1000.0, 2500.0, 4000.0, 5500.0]
    events: list[DigitalEvent] = []
    for t in press_times:
        events.append(DigitalEvent(t_ms=t, value=active, bounce_ms=8, bounce_count=7))
        events.append(DigitalEvent(t_ms=t + 400, value=idle, bounce_ms=8, bounce_count=7))
    out.append(
        Scenario(
            id=f"builtin-bounce-{pin.lower()}",
            name=f"Button bounce ({pin})",
            hypothesis="Contacts chatter for several milliseconds on every press, and each press may register many times without debounce.",
            source="builtin",
            seed=21,
            duration_ms=DURATION_MS,
            digital=[DigitalInput(pin=pin, initial=idle, events=events)],
        )
    )

    clean: list[DigitalEvent] = []
    for t in press_times:
        clean.append(DigitalEvent(t_ms=t, value=active))
        clean.append(DigitalEvent(t_ms=t + 60, value=idle))
    out.append(
        Scenario(
            id=f"builtin-shortpress-{pin.lower()}",
            name=f"Short clean presses ({pin})",
            hypothesis="A 60 ms press with no bounce is easy to miss if the firmware blocks in delay() between polls.",
            source="builtin",
            seed=22,
            duration_ms=DURATION_MS,
            digital=[DigitalInput(pin=pin, initial=idle, events=clean)],
        )
    )

    rapid: list[DigitalEvent] = []
    t = 800.0
    while t < 6500.0:
        rapid.append(DigitalEvent(t_ms=t, value=active, bounce_ms=3, bounce_count=3))
        rapid.append(DigitalEvent(t_ms=t + 150, value=idle, bounce_ms=3, bounce_count=3))
        t += 400.0
    out.append(
        Scenario(
            id=f"builtin-rapid-{pin.lower()}",
            name=f"Rapid presses ({pin})",
            hypothesis="Fast repeated presses may be missed or double counted.",
            source="builtin",
            seed=23,
            duration_ms=DURATION_MS,
            digital=[DigitalInput(pin=pin, initial=idle, events=rapid)],
        )
    )

    out.append(
        Scenario(
            id=f"builtin-floating-{pin.lower()}",
            name=f"Floating digital input ({pin})",
            hypothesis="A disconnected button wire reads random levels unless the pull-up is enabled and handled.",
            source="builtin",
            seed=24,
            duration_ms=DURATION_MS,
            floating=[FloatingWindow(pin=pin, from_ms=2000, to_ms=6000)],
            digital=[DigitalInput(pin=pin, initial=idle)],
        )
    )
    return out


def builtin_scenarios(spec: DeviceSpec, assertions: list) -> list[Scenario]:
    scenarios: list[Scenario] = []
    inputs = spec.inputs()
    for p in inputs:
        if p.type == "analog_input":
            scenarios.extend(_analog_scenarios(p, spec, assertions, inputs))
        else:
            scenarios.extend(_button_scenarios(p))
    if not scenarios:
        scenarios.append(
            Scenario(id="builtin-idle", name="Free run", hypothesis="With no inputs the firmware should simply run without crashing.", source="builtin", seed=31, duration_ms=DURATION_MS)
        )
    return [fill_defaults(s, spec, assertions) for s in scenarios]


def strip_to_harness(scenario: Scenario) -> dict:
    return scenario.harness_json()
