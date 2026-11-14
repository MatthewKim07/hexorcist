import { Report } from "./api";

export type StatTile = { key: string; value: string; label: string };

function failingScenarioCount(matrix: Report["matrix"] | undefined, iteration: string): number {
  const row = matrix?.[iteration];
  if (!row) {
    return 0;
  }
  return Object.values(row).filter((rs) => rs.some((r) => r.status === "fail")).length;
}

/** True when this run produced at least one scenario result in matrix iteration 0. */
export function hasAttackResults(report: Report | null): boolean {
  const row = report?.matrix?.["0"];
  return !!row && Object.keys(row).length > 0;
}

/** True when a verify pass produced an after matrix. */
export function hasVerifyResults(report: Report | null): boolean {
  const iter = report?.fix?.iteration;
  if (iter === undefined || iter === null) {
    return false;
  }
  const row = report?.matrix?.[String(iter)];
  return !!row && Object.keys(row).length > 0;
}

/**
 * Stat tiles for a finished report. Only includes numbers this run actually produced —
 * no Fixed / before→after / patch tiles when verify never ran.
 */
export function statTilesForReport(report: Report | null, status: string, mode: string): StatTile[] {
  if (!report) {
    return [];
  }
  if (report.contained) {
    const score = report.score;
    return [
      { key: "checks", value: `${score?.checks_passed ?? 0}/${score?.checks_total ?? 0}`, label: "checks passed" },
      { key: "secrets", value: String(report.containment?.secrets_found ?? 0), label: "secrets found" },
      { key: "containers", value: `${report.containment?.removed ?? 0}/${report.containment?.total ?? 0}`, label: "containers removed" },
    ];
  }
  if (status === "compile_failed" || status === "blocked" || status === "error" || status === "interrupted") {
    return [];
  }

  if (mode === "build") {
    const assertions = report.score?.assertions ?? report.assertions?.length ?? 0;
    const scenarios = report.score?.scenarios ?? report.scenarios?.filter((s) => !s.id.startsWith("containment-")).length ?? 0;
    const lines = report.firmware?.trim() ? report.firmware.trimEnd().split("\n").length : 0;
    const out: StatTile[] = [];
    if (hasAttackResults(report) && assertions > 0) {
      const stillBroken = (report.bugs ?? []).filter((b) => !b.verified).length;
      const passed = Math.max(0, assertions - stillBroken);
      out.push({ key: "checks", value: `${passed}/${assertions}`, label: "Checks passed" });
    }
    if (scenarios > 0 && hasAttackResults(report)) {
      out.push({ key: "scenarios", value: String(scenarios), label: "Scenarios" });
    }
    if (lines > 0) {
      out.push({ key: "firmware", value: `${lines} lines`, label: "Firmware" });
    }
    return out;
  }

  // Find bugs (break) mode — inconclusive with no attack data shows no tiles.
  if (!hasAttackResults(report)) {
    return [];
  }

  const found = report.score?.bugs_found ?? report.bugs?.length ?? 0;
  const out: StatTile[] = [{ key: "bugs", value: String(found), label: "Bugs found" }];
  if (hasVerifyResults(report)) {
    const verified = report.score?.bugs_verified ?? report.bugs?.filter((b) => b.verified).length ?? 0;
    out.push({ key: "fixed", value: `${verified}/${found || verified}`, label: "Fixed" });
    const beforeFail = failingScenarioCount(report.matrix, "0");
    const afterFail = failingScenarioCount(report.matrix, String(report.fix!.iteration));
    out.push({ key: "failing", value: `${beforeFail} → ${afterFail}`, label: "Failing scenarios" });
  }
  if (hasVerifyResults(report) && report.fix?.diff) {
    out.push({ key: "patch", value: `+${report.fix.diff.added} −${report.fix.diff.removed}`, label: "Patch" });
  }
  return out;
}
