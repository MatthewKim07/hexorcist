import { PinSpec, Trace } from "./api";

export interface Scale {
  mvPerUnit: number;
  offsetMv: number;
  unit: string;
}

/** Mirrors PinSpec.parsed_scale in the backend. */
export function parseScale(text: string): Scale {
  const m = /([-+]?\d+(?:\.\d+)?)\s*mV\s*\/\s*([^\s,;+]+)/i.exec(text ?? "");
  if (!m) {
    return { mvPerUnit: 1, offsetMv: 0, unit: "mV" };
  }
  const off = /(?:offset|\+)\s*([-+]?\d+(?:\.\d+)?)\s*mV/i.exec(text);
  return { mvPerUnit: parseFloat(m[1]) || 1, offsetMv: off ? parseFloat(off[1]) : 0, unit: m[2] };
}

export function toPhysical(mv: number, scale: Scale): number {
  return (mv - scale.offsetMv) / scale.mvPerUnit;
}

function bisectRight(values: number[], x: number): number {
  let lo = 0;
  let hi = values.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (x < values[mid]) {
      hi = mid;
    } else {
      lo = mid + 1;
    }
  }
  return lo;
}

/** Level of an output over time. analogWrite shows up as duty, -1 means plain GPIO. */
export class OutputTrack {
  times: number[] = [];
  levels: number[] = [];
  brightness: number[] = [];
  private highUntil: number[] = [];

  constructor(trace: Trace, pin: string) {
    const raw: { t: number; kind: "gpio" | "pwm"; v: number }[] = [];
    for (const e of trace.pin_events) {
      if (e.pin === pin && e.dir === "out") {
        raw.push({ t: e.t_ms, kind: "gpio", v: e.value });
      }
    }
    for (const e of trace.pwm_events) {
      if (e.pin === pin) {
        raw.push({ t: e.t_ms, kind: "pwm", v: e.duty });
      }
    }
    raw.sort((a, b) => a.t - b.t);
    let gpio = 0;
    let duty = -1;
    let level = 0;
    let bright = 0;
    let accumulated = 0;
    let lastT = 0;
    for (const r of raw) {
      if (r.kind === "gpio") {
        gpio = r.v;
      } else {
        duty = r.v;
      }
      const nextLevel = duty >= 0 ? (duty > 0 ? 1 : 0) : gpio;
      const nextBright = duty >= 0 ? duty / 255 : gpio;
      if (nextLevel !== level || nextBright !== bright) {
        if (level) {
          accumulated += r.t - lastT;
        }
        lastT = r.t;
        const toggled = nextLevel !== level;
        level = nextLevel;
        bright = nextBright;
        if (toggled || this.times.length === 0) {
          this.times.push(r.t);
          this.levels.push(level);
          this.brightness.push(bright);
          this.highUntil.push(accumulated);
        } else {
          this.brightness[this.brightness.length - 1] = bright;
        }
      }
    }
  }

  private index(t: number): number {
    return bisectRight(this.times, t) - 1;
  }

  levelAt(t: number): number {
    const i = this.index(t);
    return i >= 0 ? this.levels[i] : 0;
  }

  brightnessAt(t: number): number {
    const i = this.index(t);
    return i >= 0 ? this.brightness[i] : 0;
  }

  togglesUntil(t: number): number {
    return Math.max(0, bisectRight(this.times, t) - (this.levels[0] === 0 ? 1 : 0));
  }

  /** Total milliseconds spent HIGH before t, which drives the fan angle deterministically. */
  highTimeUntil(t: number): number {
    const i = this.index(t);
    if (i < 0) {
      return 0;
    }
    return this.highUntil[i] + (this.levels[i] ? t - this.times[i] : 0);
  }
}

export class AnalogTrack {
  times: number[] = [];
  mv: number[] = [];
  low: number[] = [];
  high: number[] = [];

  constructor(trace: Trace, pin: string) {
    for (const p of trace.input_trace) {
      if (p.pin === pin) {
        this.times.push(p.t_ms);
        this.mv.push(p.mv);
        this.low.push(p.min_mv);
        this.high.push(p.max_mv);
      }
    }
  }

  get empty(): boolean {
    return this.times.length === 0;
  }

  at(t: number): number {
    const i = bisectRight(this.times, t) - 1;
    return i >= 0 ? this.mv[i] : this.mv[0] ?? 0;
  }
}

export class InputTrack {
  times: number[] = [];
  levels: number[] = [];

  constructor(trace: Trace, pin: string, public initial: number) {
    for (const e of trace.pin_events) {
      if (e.pin === pin && e.dir === "in") {
        this.times.push(e.t_ms);
        this.levels.push(e.value);
      }
    }
  }

  at(t: number): number {
    const i = bisectRight(this.times, t) - 1;
    return i >= 0 ? this.levels[i] : this.initial;
  }
}

export type Component = "fan" | "led" | "siren" | "button" | "gauge" | "switch";

export function componentFor(pin: PinSpec): Component {
  const role = pin.role.toLowerCase();
  if (pin.type === "analog_input") {
    return "gauge";
  }
  if (pin.type === "digital_input") {
    return /switch|reed|door/.test(role) ? "switch" : "button";
  }
  if (/fan|motor|pump|blower/.test(role)) {
    return "fan";
  }
  if (/siren|buzzer|alarm|horn|bell/.test(role)) {
    return "siren";
  }
  return "led";
}

export function fmtTime(ms: number): string {
  return `${(ms / 1000).toFixed(2)} s`;
}

/** One color per pin, assigned in pin-map order so a pin keeps its color everywhere. Validated for dark surfaces. */
export const PIN_COLORS = ["#3987e5", "#d8742f", "#1fa775", "#bd8103", "#d96a9a", "#7a63e0"];
