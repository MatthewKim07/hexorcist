import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssertionResult, Report, Scenario } from "./api";
import { ReportVerdict } from "./components/ReportVerdict";
import { ScenariosTab } from "./components/Details";
import { TipProvider } from "./components/ui";
import { ScenarioResult } from "./useRun";

function pass(id: string): AssertionResult {
  return { assertion_id: id, scenario_id: "s1", type: "max_toggles", status: "pass", evidence: "ok", metrics: {}, violations: [] };
}

function fail(id: string): AssertionResult {
  return { assertion_id: id, scenario_id: "s2", type: "max_toggles", status: "fail", evidence: "toggled 10", metrics: {}, violations: [] };
}

function scenario(id: string, name: string): Scenario {
  return { id, name, hypothesis: name, source: "builtin", duration_ms: 1000 };
}

function result(id: string, name: string, passed: boolean): ScenarioResult {
  return { iteration: 0, scenario_id: id, name, passed, failed: passed ? [] : ["a1"], exit_reason: "completed", duration_ms: 10 };
}

/** Inconclusive fixture: attack matrix exists, verify never ran. */
function inconclusiveReport(): Report {
  return {
    status: "inconclusive",
    firmware: "void setup(){}\nvoid loop(){}\n",
    spec: { pins: [], behaviour: "Thermostat" },
    device_model: null,
    assertions: [{ id: "a1", type: "max_toggles", description: "Fan stays calm", output_pin: "D9" }],
    scenarios: [scenario("s1", "Nominal"), scenario("s2", "Glitch")],
    matrix: { "0": { s1: [pass("a1")], s2: [fail("a1")] } },
    iterations: [],
    bugs: [
      {
        id: "b1",
        assertion_id: "a1",
        assertion_type: "max_toggles",
        requirement: "calm",
        title: "Fan chatters",
        severity: "high",
        root_cause: "No hysteresis",
        code_lines: [12],
        scenario_id: "s2",
        scenario_name: "Glitch",
        evidence: "toggled 10",
        failing_scenarios: [{ id: "s2", name: "Glitch", evidence: "toggled 10" }],
        before: { status: "fail", evidence: "toggled 10" },
        after: null,
        verified: false,
      },
    ],
    compile_log: "",
    error: "",
    warnings: ["LLM unreachable during fix"],
    containment: { records: [], total: 0, removed: 0, secrets_found: 0, timeouts: 0, oom_kills: 0, network_none: null, violations: 0 },
    llm: { model: "test", calls: 2, repairs: 0, prompt_tokens: 0, completion_tokens: 0 },
    score: { bugs_found: 1, bugs_verified: 0, scenarios: 2, assertions: 1, fix_attempts: 0 },
  };
}

describe("inconclusive report without verify", () => {
  it("does not show Fixed, before→after failing counts, or all passing", () => {
    const report = inconclusiveReport();
    const beforeResults = {
      s1: result("s1", "Nominal", true),
      s2: result("s2", "Glitch", false),
    };

    const { container } = render(
      <TipProvider>
        <ReportVerdict report={report} status="inconclusive" firstWarning={report.warnings[0]} createdAt={1} finishedAt={2} mode="break" />
        <ScenariosTab
          scenarios={report.scenarios}
          beforeResults={beforeResults}
          afterResults={null}
          beforeMatrix={report.matrix["0"]}
          afterMatrix={undefined}
          assertions={report.assertions}
          pins={[]}
          selected={null}
          onSelect={() => {}}
        />
      </TipProvider>,
    );

    const text = container.textContent ?? "";
    expect(screen.getByText("Inconclusive")).toBeTruthy();
    expect(text).not.toMatch(/\bFixed\b/);
    expect(text).not.toContain("10 → 0");
    expect(text).not.toContain("all passing");
  });
});
