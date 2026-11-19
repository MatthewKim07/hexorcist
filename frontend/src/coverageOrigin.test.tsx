import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AssertionDef, AssertionResult } from "./api";
import { ChecksTab } from "./components/Details";
import { TipProvider } from "./components/ui";

const result = (id: string): AssertionResult => ({ assertion_id: id, scenario_id: "s1", type: "serial_period", status: "pass", evidence: "ok", metrics: {}, violations: [] });
const def = (id: string, origin?: string): AssertionDef => ({ id, description: `check ${id}`, type: "serial_period", pattern: "^x", period_ms: 1000, tolerance_ms: 100, ...(origin ? { origin } : {}) }) as AssertionDef;

function show(assertions: AssertionDef[]) {
  render(
    <TipProvider>
      <ChecksTab results={assertions.map((a) => result(a.id))} assertions={assertions} scenarioName="Nominal" side="run" />
    </TipProvider>,
  );
}

describe("check origin", () => {
  afterEach(cleanup);

  it("names the spec coverage step next to a check it added, and only that one", () => {
    show([def("a1"), def("a2", "coverage")]);
    expect(screen.getAllByText("Added by the spec coverage step")).toHaveLength(1);
    expect(screen.getByText("check a2").parentElement?.textContent).toContain("Added by the spec coverage step");
    expect(screen.getByText("check a1").parentElement?.textContent).not.toContain("coverage");
  });

  it("shows nothing extra when no check has an origin", () => {
    show([def("a1"), def("a2")]);
    expect(screen.queryByText("Added by the spec coverage step")).toBeNull();
  });
});
