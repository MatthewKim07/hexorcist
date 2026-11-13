import { PinType } from "./api";

/** A name for the sketch: its first comment line, or a plain file name. */
export function sketchName(firmware: string): string {
  for (const line of firmware.split("\n")) {
    const text = line.trim().replace(/^\/\/+|^\/\*+|\*+\/$/g, "").trim();
    if (text) {
      return line.trim().startsWith("//") || line.trim().startsWith("/*") ? (text.length > 34 ? `${text.slice(0, 33)}…` : text) : "sketch.ino";
    }
  }
  return "sketch.ino";
}

export function lineCount(firmware: string): number {
  return firmware.trim() ? firmware.trimEnd().split("\n").length : 0;
}

export interface Mentioned {
  pin: string;
  type: PinType;
  active_low: boolean;
}

/** Pins the sketch drives or reads, guessed from pinMode and the read and write calls. Only a suggestion for wiring. */
export function mentionedPins(firmware: string): Mentioned[] {
  const code = firmware.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  const names = new Map<string, string>();
  for (const m of code.matchAll(/#define\s+(\w+)\s+(A?\d+)\b/g)) {
    names.set(m[1], m[2]);
  }
  for (const m of code.matchAll(/\b(?:const\s+)?(?:int|byte|uint8_t|short)\s+(\w+)\s*=\s*(A?\d+)\s*;/g)) {
    names.set(m[1], m[2]);
  }
  const resolve = (token: string, analog: boolean): string | null => {
    const raw = names.get(token) ?? token;
    if (/^A[0-5]$/.test(raw)) {
      return raw;
    }
    if (/^\d+$/.test(raw)) {
      const n = Number(raw);
      if (analog && n <= 5) {
        return `A${n}`;
      }
      return n >= 2 && n <= 13 ? `D${n}` : null;
    }
    return null;
  };
  const found = new Map<string, Mentioned>();
  const note = (pin: string | null, type: PinType, active_low = false) => {
    if (pin && (!found.has(pin) || type === "pwm_output")) {
      found.set(pin, { pin, type, active_low });
    }
  };
  for (const m of code.matchAll(/pinMode\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)/g)) {
    note(resolve(m[1], false), m[2] === "OUTPUT" ? "digital_output" : "digital_input", m[2] === "INPUT_PULLUP");
  }
  for (const m of code.matchAll(/analogRead\s*\(\s*(\w+)\s*\)/g)) {
    note(resolve(m[1], true), "analog_input");
  }
  for (const m of code.matchAll(/analogWrite\s*\(\s*(\w+)\s*,/g)) {
    note(resolve(m[1], false), "pwm_output");
  }
  for (const m of code.matchAll(/digitalWrite\s*\(\s*(\w+)\s*,/g)) {
    note(resolve(m[1], false), "digital_output");
  }
  for (const m of code.matchAll(/digitalRead\s*\(\s*(\w+)\s*\)/g)) {
    note(resolve(m[1], false), "digital_input");
  }
  return [...found.values()];
}
