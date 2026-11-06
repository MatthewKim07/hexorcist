import { Bug } from "./api";

const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3 } as const;

/** Most severe first. The sort is stable, so ties keep the order the backend found them in. */
export function rankBugs(bugs: Bug[]): Bug[] {
  return [...bugs].sort((a, b) => (SEVERITY_RANK[a.severity] ?? 4) - (SEVERITY_RANK[b.severity] ?? 4));
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
    return `${after[1]} switched ${after[2]}× in ${seconds(parseFloat(after[3]) * 1000)}`;
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
  const m = /(?<!\w)(\d[\d.,]*\s?(?:×|ms|s|mV|V|°C|%)(?![a-z])(?:\s+in\s+\d[\d.,]*\s?s)?)/.exec(fact);
  return m ? m[1] : "";
}

export function duration(from: number, to: number | null): string {
  if (to === null) {
    return "";
  }
  const s = Math.round(to - from);
  return s >= 60 ? `${Math.floor(s / 60)} m ${String(s % 60).padStart(2, "0")} s` : `${s} s`;
}
