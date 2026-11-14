import { Bug } from "./api";

const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3 } as const;

/**
 * How much a bug shows on the virtual board. A chattering output or a miscounted toggle is visible on the board
 * itself, a missed or short pulse and a wrong safe state are visible on a pin, and a serial-only bug shows only in text.
 */
const VISUAL_RANK: Record<string, number> = {
  max_toggles: 0,
  toggle_per_press: 0,
  timed_pulse: 1,
  output_follows: 1,
  safe_state_on_fault: 1,
  responsive: 2,
  serial_period: 2,
  serial_value_matches: 2,
};

/**
 * The bug to show first: most visual evidence, then most severe. The sort is stable, so ties keep the order the
 * backend found them in.
 */
export function rankBugs(bugs: Bug[]): Bug[] {
  const visual = (b: Bug) => VISUAL_RANK[b.assertion_type] ?? 3;
  return [...bugs].sort((a, b) => visual(a) - visual(b) || (SEVERITY_RANK[a.severity] ?? 4) - (SEVERITY_RANK[b.severity] ?? 4));
}

function seconds(ms: number): string {
  const s = ms / 1000;
  return `${Number.isInteger(s) ? s : s.toFixed(1)} s`;
}

/**
 * The one measured number from an evidence sentence, as a short phrase ("D9 switched 23× in 5 s").
 * The backend writes plain sentences, so this reads the common shapes and otherwise falls back to the
 * first clause. It never invents a number that is not in the sentence.
 */
export function keyFact(evidence: string | undefined | null): string {
  if (!evidence) {
    return "";
  }
  const toggled = /^(\w+) toggled (\d+) times? in a (\d+) ms window/.exec(evidence);
  if (toggled) {
    return `${toggled[1]} switched ${toggled[2]}× in ${seconds(Number(toggled[3]))}`;
  }
  const after = /^(\w+) toggled (\d+) time\(s\) in ([\d.]+) ?s/.exec(evidence);
  if (after) {
    const span = seconds(parseFloat(after[3]) * 1000);
    return after[2] === "0" ? `${after[1]} held steady: 0 switches in ${span}` : `${after[1]} switched ${after[2]}× in ${span}`;
  }
  const wrong = /^(\w+) was in the wrong state for (\d+) ms/.exec(evidence);
  if (wrong) {
    return `${wrong[1]} wrong for ${seconds(Number(wrong[2]))}`;
  }
  const noSafe = /(\w+) was not in safe state \w+ for (\d+) ms/.exec(evidence);
  if (noSafe) {
    return `${noSafe[1]} not safe for ${seconds(Number(noSafe[2]))}`;
  }
  const safe = /(\w+) reached safe state \w+ within (\d+) ms/.exec(evidence);
  if (safe) {
    return `${safe[1]} safe within ${seconds(Number(safe[2]))}`;
  }
  const missed = /^(\w+) missed (\d+) of (\d+) trigger/.exec(evidence);
  if (missed) {
    return `${missed[1]} missed ${missed[2]} of ${missed[3]} triggers`;
  }
  const pulses = /^(\w+) ran (\d+) pulse\(s\), lasting \d+ to (\d+) ms/.exec(evidence);
  if (pulses) {
    return `${pulses[1]} ran ${pulses[2]} pulses of ${seconds(Number(pulses[3]))}`;
  }
  const silent = /went silent for (\d+) ms/.exec(evidence);
  if (silent) {
    return `silent for ${seconds(Number(silent[1]))}`;
  }
  const gap = /^Longest silent gap was (\d+) ms/.exec(evidence);
  if (gap) {
    return `longest silence ${seconds(Number(gap[1]))}`;
  }
  const press = /^(\d+) of (\d+) press\(es\) did not toggle (\w+) exactly once/.exec(evidence);
  if (press) {
    return `${press[3]} wrong on ${press[1]} of ${press[2]} presses`;
  }
  const pressOk = /^All (\d+) press\(es\) toggled (\w+) exactly once/.exec(evidence);
  if (pressOk) {
    return `${pressOk[2]} toggled once on all ${pressOk[1]} presses`;
  }
  const off = /: off by ([\d.]+ ?\S+) \(tolerance/.exec(evidence);
  if (off) {
    return `off by ${off[1]}`;
  }
  const within = /^(\d+) printed values within (±[\d.]+ ?\S+)/.exec(evidence);
  if (within) {
    return `${within[1]} values within ${within[2]}`;
  }
  return clip(firstClause(evidence), 72);
}

function firstClause(text: string): string {
  const cut = text.split(/(?:, first at|\. |: )/)[0];
  return cut.replace(/\.$/, "");
}

export function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

/** The number alone, for a list row: "23× in 5 s". */
export function keyNumber(evidence: string | undefined | null): string {
  const fact = keyFact(evidence);
  if (fact.startsWith("off by")) {
    return fact;
  }
  const m = /(?<!\w)(\d[\d.,]*\s?(?:×|ms|s|mV|V|°C|%)(?![a-z])(?:\s+in\s+\d[\d.,]*\s?s)?)/.exec(fact);
  return m ? m[1] : clip(fact.replace(/^[AD]\d+ /, ""), 32);
}

export function duration(from: number, to: number | null): string {
  if (to === null) {
    return "";
  }
  const s = Math.round(to - from);
  return s >= 60 ? `${Math.floor(s / 60)} min ${s % 60} s` : `${s} s`;
}

/** Compact run duration for tables: "33s", "1m 23s", "1h 16m". */
export function shortDuration(from: number, to: number | null): string {
  if (to === null) {
    return "";
  }
  const s = Math.max(0, Math.round(to - from));
  if (s < 60) {
    return `${s}s`;
  }
  const m = Math.floor(s / 60);
  if (m < 60) {
    const rem = s % 60;
    return rem === 0 ? `${m}m` : `${m}m ${rem}s`;
  }
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM === 0 ? `${h}h` : `${h}h ${remM}m`;
}
