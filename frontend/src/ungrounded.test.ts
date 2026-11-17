import { describe, expect, it } from "vitest";
import { unconfirmedIds } from "./reportStats";
import { verdictText } from "./components/ReportVerdict";
import type { Report } from "./api";

const base = { assertions: [], cross_check: undefined } as unknown as Pick<Report, "cross_check" | "assertions" | "ungrounded">;

describe("ungrounded requirements", () => {
  it("are ignored like unconfirmed checks, from the list or from the assertion flag", () => {
    const fromList = unconfirmedIds({ ...base, ungrounded: [{ assertion_id: "a3" } as never] });
    expect([...fromList]).toEqual(["a3"]);
    const fromFlag = unconfirmedIds({ ...base, assertions: [{ id: "a2", ungrounded: true } as never, { id: "a1" } as never] });
    expect([...fromFlag]).toEqual(["a2"]);
  });

  it("are named in the all-clear sentence and taken out of the passed count", () => {
    const report = { score: { bugs_found: 0, bugs_verified: 0, scenarios: 10, assertions: 6, fix_attempts: 0, possible_ambiguities: 1, ungrounded_requirements: 2 } } as unknown as Report;
    const v = verdictText(report, "clean", "");
    expect(v.title).toBe("No bugs found");
    expect(v.detail).toBe("3 checks passed in 10 scenarios. 1 possible spec ambiguity, 2 checks left out for asking more than the spec states, listed below");
  });

  it("leave the old sentence alone when nothing was left out", () => {
    const report = { score: { bugs_found: 0, bugs_verified: 0, scenarios: 10, assertions: 6, fix_attempts: 0 } } as unknown as Report;
    expect(verdictText(report, "clean", "").detail).toBe("6 checks passed in 10 scenarios");
  });
});
