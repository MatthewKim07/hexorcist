import { useState } from "react";
import { ChevronDown, CircleCheck, CircleX, Minus } from "lucide-react";
import { AssertionDef, AssertionResult, PinSpec, Report, Scenario, Trace } from "../api";
import { chipLabel } from "../checks";
import { iconProps } from "../icons";
import { RunState } from "../useRun";
import { Fold, Tip } from "./ui";

type ScenarioResult = RunState["results"][number][string] | undefined;

function scenarioFailed(r: ScenarioResult): boolean {
  return !!r && !r.passed;
}

function failTip(results: AssertionResult[] | undefined, assertions: AssertionDef[], pins: PinSpec[]): string {
  const fails = (results ?? []).filter((x) => x.status === "fail");
  if (!fails.length) {
    return "Passed";
  }
  return fails
    .map((f) => {
      const a = assertions.find((x) => x.id === f.assertion_id);
      return a ? `Failed: ${chipLabel(a, pins)}` : `Failed: ${f.type}`;
    })
    .join(" · ");
}

function SideIcon({ results, assertions, pins }: { results: AssertionResult[] | undefined; assertions: AssertionDef[]; pins: PinSpec[] }) {
  if (!results) {
    return <Minus {...iconProps} className="text-muted" />;
  }
  const fail = results.some((r) => r.status === "fail");
  const tip = failTip(results, assertions, pins);
  return (
    <Tip content={tip}>
      <span tabIndex={0} className="inline-flex" aria-label={tip}>
        {fail ? <CircleX {...iconProps} className="text-fail" /> : <CircleCheck {...iconProps} className="text-pass" />}
      </span>
    </Tip>
  );
}

/** Scenarios table: Before/After for break+verify, single Result for build or attack-only. */
export function ScenariosTab({
  scenarios,
  beforeResults,
  afterResults,
  beforeMatrix,
  afterMatrix,
  assertions,
  pins,
  selected,
  onSelect,
  buildMode = false,
}: {
  scenarios: Scenario[];
  beforeResults: RunState["results"][number];
  afterResults: RunState["results"][number] | null;
  beforeMatrix: Report["matrix"][string] | undefined;
  afterMatrix: Report["matrix"][string] | undefined;
  assertions: AssertionDef[];
  pins: PinSpec[];
  selected: string | null;
  onSelect: (id: string) => void;
  buildMode?: boolean;
}) {
  const [showPassed, setShowPassed] = useState(false);
  const hasAfter = !buildMode && (!!afterMatrix || !!afterResults);
  const resultLabel = buildMode || !hasAfter ? "Result" : "Before";

  const rank = (s: Scenario) => {
    const before = beforeResults[s.id];
    if (scenarioFailed(before)) {
      return 0;
    }
    return 1;
  };
  const sorted = [...scenarios].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  const failedBefore = sorted.filter((s) => rank(s) === 0);
  const passedBoth = sorted.filter((s) => {
    if (rank(s) === 0) {
      return false;
    }
    if (!hasAfter) {
      return !!beforeResults[s.id]?.passed;
    }
    const after = afterResults?.[s.id];
    return !!beforeResults[s.id]?.passed && !!after?.passed;
  });
  const other = sorted.filter((s) => !failedBefore.includes(s) && !passedBoth.includes(s));
  const primary = [...failedBefore, ...other];

  const summary = (() => {
    if (buildMode) {
      return failedBefore.length ? `${scenarios.length} scenarios, ${failedBefore.length} failed` : `${scenarios.length} scenarios`;
    }
    if (hasAfter) {
      return `${scenarios.length} scenarios${failedBefore.length ? `, ${failedBefore.length} failed before` : ", all passing"}`;
    }
    return failedBefore.length ? `${scenarios.length} scenarios, ${failedBefore.length} failed` : `${scenarios.length} scenarios`;
  })();

  const collapsedLabel = buildMode || !hasAfter ? `${passedBoth.length} passed` : `${passedBoth.length} passed before and after`;
  const colSpan = hasAfter ? 3 : 2;

  const row = (s: Scenario) => (
    <tr
      key={s.id}
      className={`cursor-pointer border-b border-line transition-colors last:border-b-0 hover:bg-[#FAFAFA] ${selected === s.id ? "bg-[#FAFAFA]" : ""}`}
      onClick={() => onSelect(s.id)}
    >
      <td className="py-2.5 pr-4 align-middle">
        <Tip content={s.hypothesis}>
          <span tabIndex={0} className={selected === s.id ? "font-medium text-ink" : "text-ink"}>
            {s.name}
          </span>
        </Tip>
      </td>
      <td className="py-2.5 text-center align-middle">
        <SideIcon results={beforeMatrix?.[s.id] ?? undefined} assertions={assertions} pins={pins} />
      </td>
      {hasAfter && (
        <td className="py-2.5 text-center align-middle">
          <SideIcon results={afterMatrix?.[s.id] ?? undefined} assertions={assertions} pins={pins} />
        </td>
      )}
    </tr>
  );

  return (
    <div className="pt-4">
      <p className="mb-3 text-xs text-muted">{summary}</p>
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="pb-2 pr-4 font-normal">Name</th>
            <th className="w-14 pb-2 text-center font-normal">{resultLabel}</th>
            {hasAfter && <th className="w-14 pb-2 text-center font-normal">After</th>}
          </tr>
        </thead>
        <tbody>
          {primary.map(row)}
          {passedBoth.length > 0 && (
            <>
              <tr className="border-b border-line">
                <td colSpan={colSpan} className="py-0">
                  <button type="button" className="flex w-full items-center gap-2 py-2.5 text-left text-sm text-muted hover:text-ink" aria-expanded={showPassed} onClick={() => setShowPassed((v) => !v)}>
                    <CircleCheck {...iconProps} className="text-pass" />
                    <span className="flex-1">{collapsedLabel}</span>
                    <ChevronDown {...iconProps} className={`transition-transform ${showPassed ? "rotate-180" : ""}`} />
                  </button>
                </td>
              </tr>
              {showPassed && passedBoth.map(row)}
            </>
          )}
        </tbody>
      </table>
    </div>
  );
}

/** The checks that ran in the scenario on the board, with what each one measured. */
export function ChecksTab({ results, assertions, scenarioName, side }: { results: AssertionResult[]; assertions: AssertionDef[]; scenarioName: string; side: string }) {
  const names = new Map(assertions.map((a) => [a.id, a.description]));
  const failed = results.filter((r) => r.status === "fail").length;
  return (
    <div className="pt-4">
      <p className="mb-3 text-xs text-muted">
        {scenarioName}, {side}: {results.length - failed} of {results.length} passed
      </p>
      {results.length === 0 && <p className="text-sm text-muted">No results for this scenario yet.</p>}
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="w-8 pb-2 font-normal" />
            <th className="pb-2 pr-4 font-normal">Check</th>
            <th className="hidden pb-2 font-normal sm:table-cell">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={r.assertion_id} className="border-b border-line last:border-b-0">
              <td className="py-2.5 align-middle">
                {r.status === "pass" && <CircleCheck {...iconProps} className="text-pass" />}
                {r.status === "fail" && <CircleX {...iconProps} className="text-fail" />}
                {r.status === "not_exercised" && <Minus {...iconProps} className="text-muted" />}
              </td>
              <td className="py-2.5 pr-4 align-middle text-ink">
                {names.get(r.assertion_id) ?? r.type}
                <span className="mt-0.5 block text-xs text-muted sm:hidden">{r.evidence}</span>
              </td>
              <td className="hidden py-2.5 align-middle font-mono text-xs text-muted sm:table-cell">{r.evidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Serial output, compiler output, warnings and run details. */
export function LogsTab({
  trace,
  report,
  warnings,
  deviceModel,
  hideCompile = false,
}: {
  trace: Trace | null;
  report: Report | null;
  warnings: string[];
  deviceModel: Report["device_model"];
  hideCompile?: boolean;
}) {
  const llm = report?.llm;
  const hasSerial = !!trace && trace.serial_log.length > 0;
  return (
    <div className="space-y-5 pt-4">
      {hasSerial && (
        <Fold title={`Serial output (${trace.serial_log.length})`} defaultOpen contentClassName="pl-5">
          <div className="scroll max-h-[260px] overflow-auto rounded-md border border-line bg-[#FAFAFA] p-3 font-mono text-[13px] leading-5">
            {trace.serial_log.slice(0, 400).map((l, i) => (
              <div key={i} className="flex gap-3 whitespace-pre">
                <span className="shrink-0 text-muted">{(l.t_ms / 1000).toFixed(3)}</span>
                <span>{l.text}</span>
              </div>
            ))}
          </div>
        </Fold>
      )}
      {!hideCompile && report?.compile_log && (
        <Fold title="Compiler output" contentClassName="pl-5">
          <pre className="scroll max-h-64 overflow-auto rounded-md border border-line bg-[#FAFAFA] p-3 font-mono text-[13px] text-muted">{report.compile_log}</pre>
        </Fold>
      )}
      {warnings.length > 0 && (
        <Fold title={`Warnings (${warnings.length})`} contentClassName="pl-5">
          <ul className="space-y-2 text-xs text-muted">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Fold>
      )}
      {deviceModel && (
        <Fold title="What the agent understood" contentClassName="pl-5">
          <p className="text-xs text-muted">{deviceModel.summary}</p>
          {deviceModel.risks.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-muted">
              {deviceModel.risks.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </Fold>
      )}
      {llm && llm.calls > 0 && (
        <p className="num pt-2 text-xs text-muted">
          {llm.model}: {llm.calls} calls, {llm.repairs} repairs, {llm.prompt_tokens + llm.completion_tokens} tokens
        </p>
      )}
    </div>
  );
}
