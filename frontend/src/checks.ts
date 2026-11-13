import { Check, PinSpec } from "./api";
import { parseScale } from "./trace";

/**
 * Short labels for checks, built from their parameters rather than the model's prose, so a label
 * always says what the engine will measure, including after the user edits a number.
 */

const OPS: Record<string, string> = { ">=": "≥", "<=": "≤", ">": ">", "<": "<", "==": "=", "!=": "≠" };

function trim(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
}

export function ms(n: number): string {
  return n >= 1000 ? `${trim(n / 1000)} s` : `${trim(n)} ms`;
}

function pinOf(pins: PinSpec[], pin: string | undefined): PinSpec | undefined {
  return pins.find((p) => p.pin === pin);
}

export function shortRole(pin: PinSpec | undefined, fallback = ""): string {
  const role = (pin?.role ?? "").replace(/\s*\(.*\)/, "").trim();
  return role || pin?.pin || fallback;
}

function unitOf(pins: PinSpec[], pin: string): string {
  const p = pinOf(pins, pin);
  return p?.type === "analog_input" ? parseScale(p.scale).unit : "";
}

interface Condition {
  pin: string;
  op: string;
  value: number;
}

function condition(c: Condition, pins: PinSpec[]): string {
  const p = pinOf(pins, c.pin);
  if (p && p.type === "digital_input") {
    const pressedLevel = p.active_low ? 0 : 1;
    const pressed = (c.op === "==" && c.value === pressedLevel) || (c.op === "!=" && c.value !== pressedLevel);
    return pressed ? "pressed" : "released";
  }
  const unit = unitOf(pins, c.pin);
  return `${OPS[c.op] ?? c.op} ${trim(c.value)}${unit ? ` ${unit}` : ""}`;
}

function serialText(pattern: string): string {
  const plain = pattern.replace(/^\^/, "").replace(/\$$/, "");
  return /[[\](){}*+?\\|.]/.test(plain) ? "A line" : `"${plain}"`;
}

/** The chip text: "≤ 2 switches / 5 s", "Fan ON if < 2 °C", "\"hb\" every 500 ms". */
export function chipLabel(c: Check, pins: PinSpec[]): string {
  switch (c.type) {
    case "output_follows": {
      if (c.mode === "edge" && c.high_when) {
        const when = condition(c.high_when, pins);
        return when === "pressed" ? `ON within ${ms(c.within_ms)} of a press` : `ON within ${ms(c.within_ms)} at ${when}`;
      }
      const on = c.high_when ? condition(c.high_when, pins) : "";
      const off = c.low_when ? condition(c.low_when, pins) : "";
      if (on && off) {
        return on === "pressed" ? "ON while pressed" : `ON ${on}, OFF ${off}`;
      }
      return on ? `ON while ${on}` : `OFF while ${off}`;
    }
    case "max_toggles":
      return `≤ ${c.max_toggles} switch${c.max_toggles === 1 ? "" : "es"} / ${ms(c.window_ms)}`;
    case "safe_state_on_fault": {
      const out = shortRole(pinOf(pins, c.output_pin), c.output_pin);
      const state = c.safe_value ? "ON" : "OFF";
      return c.fault_when ? `${out} ${state} if ${condition(c.fault_when, pins)}` : `${out} ${state} if ${c.floating_pin} floats`;
    }
    case "toggle_per_press":
      return "1 toggle per press";
    case "timed_pulse":
      return `ON ${ms(c.duration_ms)} per press`;
    case "serial_period":
      return `${serialText(c.pattern ?? "")} every ${ms(c.period_ms)}`;
    case "serial_value_matches": {
      const unit = unitOf(pins, c.input_pin);
      return `Prints ${c.input_pin} within ±${trim(c.tolerance)}${unit ? ` ${unit}` : ""}`;
    }
    case "responsive":
      return `Never silent > ${ms(c.max_gap_ms)}`;
    case "no_crash":
      return "No crash or hang";
    default:
      return c.type.replace(/_/g, " ");
  }
}

/** Where the check sits on the board: beside the part it constrains, or beside the USB port for serial and timing. */
export function anchorOf(c: Check): string {
  switch (c.type) {
    case "output_follows":
    case "max_toggles":
    case "timed_pulse":
      return c.pin;
    case "toggle_per_press":
      return c.output_pin;
    case "safe_state_on_fault":
      return c.fault_when?.pin ?? c.floating_pin ?? c.output_pin;
    default:
      return "usb";
  }
}

export interface Field {
  path: string[];
  label: string;
  unit: string;
}

/** The numbers a user may change in a check. Pins, levels and patterns stay as read from the text. */
export function fieldsOf(c: Check, pins: PinSpec[]): Field[] {
  const analog = (cond: Condition | undefined, path: string, label: string): Field[] => (cond && unitOf(pins, cond.pin) ? [{ path: [path, "value"], label, unit: unitOf(pins, cond.pin) }] : []);
  switch (c.type) {
    case "output_follows":
      return [...analog(c.high_when, "high_when", "On at"), ...analog(c.low_when, "low_when", "Off at"), { path: ["within_ms"], label: "Within", unit: "ms" }];
    case "max_toggles":
      return [
        { path: ["max_toggles"], label: "At most", unit: "switches" },
        { path: ["window_ms"], label: "In any", unit: "ms" },
      ];
    case "safe_state_on_fault":
      return [...analog(c.fault_when, "fault_when", "Fault at"), { path: ["within_ms"], label: "Within", unit: "ms" }];
    case "toggle_per_press":
      return [{ path: ["within_ms"], label: "Within", unit: "ms" }];
    case "timed_pulse":
      return [
        { path: ["duration_ms"], label: "On for", unit: "ms" },
        { path: ["within_ms"], label: "Starts within", unit: "ms" },
      ];
    case "serial_period":
      return [
        { path: ["period_ms"], label: "Every", unit: "ms" },
        { path: ["tolerance_ms"], label: "Give or take", unit: "ms" },
      ];
    case "serial_value_matches":
      return [{ path: ["tolerance"], label: "Within ±", unit: unitOf(pins, c.input_pin) }];
    case "responsive":
      return [{ path: ["max_gap_ms"], label: "Silent at most", unit: "ms" }];
    default:
      return [];
  }
}

export function readField(c: Check, path: string[]): number {
  return path.reduce<any>((v, k) => v?.[k], c) as number;
}

/** A copy with one number changed. Its description is rewritten from the new numbers, so it never contradicts them. */
export function withField(c: Check, path: string[], value: number, pins: PinSpec[]): Check {
  const next = structuredClone(c);
  let at: any = next;
  for (const k of path.slice(0, -1)) {
    at = at[k];
  }
  at[path[path.length - 1]] = value;
  const subject = anchorOf(next) === "usb" ? "Firmware" : shortRole(pinOf(pins, anchorOf(next)), anchorOf(next));
  next.description = `${subject}: ${chipLabel(next, pins)}`;
  return next;
}
