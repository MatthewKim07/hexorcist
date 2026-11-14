import { CircleCheck, CircleX, Minus } from "lucide-react";
import { AssertionDef, AssertionResult, Report, Scenario, Trace } from "../api";
import { iconProps } from "../icons";
import { RunState } from "../useRun";
import { Fold, Tip } from "./ui";

/** Scenarios, failing ones first. A click puts the scenario on the board. */
export function ScenariosTab({ scenarios, results, selected, onSelect }: { scenarios: Scenario[]; results: RunState["results"][number]; selected: string | null; onSelect: (id: string) => void }) {
  const rank = (s: Scenario) => (results[s.id] && !results[s.id].passed ? 0 : 1);
  const sorted = [...scenarios].sort((a, b) => rank(a) - rank(b));
  const failing = scenarios.filter((s) => rank(s) === 0).length;
  return (
    <div className="pt-4">
      <p className="mb-3 text-xs text-muted">
        {scenarios.length} scenarios{failing ? `, ${failing} failing` : ", all passing"}
      </p>
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="w-8 pb-2 font-normal" />
            <th className="pb-2 pr-4 font-normal">Name</th>
            <th className="pb-2 text-right font-normal">Result</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => {
            const r = results[s.id];
            return (
              <tr
                key={s.id}
                className={`cursor-pointer border-b border-line transition-colors last:border-b-0 hover:bg-[#FAFAFA] ${selected === s.id ? "bg-[#FAFAFA]" : ""}`}
                onClick={() => onSelect(s.id)}
              >
                <td className="py-2.5 align-middle">
                  {!r ? <Minus {...iconProps} className="text-muted" /> : r.passed ? <CircleCheck {...iconProps} className="text-pass" /> : <CircleX {...iconProps} className="text-fail" />}
                </td>
                <td className="py-2.5 pr-4 align-middle">
                  <Tip content={s.hypothesis}>
                    <span tabIndex={0} className={selected === s.id ? "font-medium text-ink" : "text-ink"}>
                      {s.name}
                    </span>
                  </Tip>
                </td>
                <td className="num py-2.5 text-right align-middle text-xs text-muted">
                  {!r ? "—" : r.passed ? "Pass" : r.failed.length ? `${r.failed.length} failed` : r.exit_reason}
                </td>
              </tr>
            );
          })}
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
export function LogsTab({ trace, report, warnings, deviceModel }: { trace: Trace | null; report: Report | null; warnings: string[]; deviceModel: Report["device_model"] }) {
  const llm = report?.llm;
  return (
    <div className="space-y-5 pt-4">
      <Fold title={`Serial output${trace ? ` (${trace.serial_log.length})` : ""}`} defaultOpen contentClassName="pl-5">
        <div className="scroll max-h-[260px] overflow-auto rounded-md border border-line bg-[#FAFAFA] p-3 font-mono text-[13px] leading-5">
          {!trace || trace.serial_log.length === 0 ? (
            <span className="text-muted">No output</span>
          ) : (
            trace.serial_log.slice(0, 400).map((l, i) => (
              <div key={i} className="flex gap-3 whitespace-pre">
                <span className="shrink-0 text-muted">{(l.t_ms / 1000).toFixed(3)}</span>
                <span>{l.text}</span>
              </div>
            ))
          )}
        </div>
      </Fold>
      {report?.compile_log && (
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
