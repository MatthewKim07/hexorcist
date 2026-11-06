import { ReactNode } from "react";
import { AssertionDef, AssertionResult, Report, Scenario, Trace } from "../api";
import { RunState } from "../useRun";
import { Icon } from "./Common";

/** Scenarios, failing ones first. A click puts the scenario on the board. */
export function ScenariosTab({ scenarios, results, selected, onSelect }: { scenarios: Scenario[]; results: RunState["results"][number]; selected: string | null; onSelect: (id: string) => void }) {
  const rank = (s: Scenario) => (results[s.id] && !results[s.id].passed ? 0 : 1);
  const sorted = [...scenarios].sort((a, b) => rank(a) - rank(b));
  const failing = scenarios.filter((s) => rank(s) === 0).length;
  return (
    <div className="py-6">
      <p className="label mb-3">
        {scenarios.length} scenarios{failing ? `, ${failing} failing` : ", all passing"}
      </p>
      <ul className="grid gap-x-12 md:grid-cols-2">
        {sorted.map((s) => {
          const r = results[s.id];
          return (
            <li key={s.id} className="border-b border-line">
              <button title={s.hypothesis} onClick={() => onSelect(s.id)} className={`flex w-full items-center gap-3 py-2.5 text-left hover:text-ink ${selected === s.id ? "text-ink" : "text-muted"}`}>
                <span className="w-4 shrink-0">{!r ? <span className="pulse-soft block h-1.5 w-1.5 rounded-full bg-faint" /> : r.passed ? <Icon name="check" className="text-pass" /> : <Icon name="x" className="text-fail" />}</span>
                <span className="min-w-0 flex-1">{s.name}</span>
                {r && !r.passed && <span className="num text-fail">{r.failed.length ? r.failed.length : r.exit_reason}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The checks that ran in the scenario on the board, with what each one measured. */
export function ChecksTab({ results, assertions, scenarioName, side }: { results: AssertionResult[]; assertions: AssertionDef[]; scenarioName: string; side: string }) {
  const names = new Map(assertions.map((a) => [a.id, a.description]));
  const failed = results.filter((r) => r.status === "fail").length;
  return (
    <div className="py-6">
      <p className="label mb-3">
        {scenarioName}, {side}: {results.length - failed} of {results.length} passed
      </p>
      {results.length === 0 && <p className="text-faint">No results for this scenario yet.</p>}
      <ul>
        {results.map((r) => (
          <li key={r.assertion_id} className="flex gap-3 border-b border-line py-3">
            <span className="mt-1 w-4 shrink-0">
              {r.status === "pass" && <Icon name="check" className="text-pass" />}
              {r.status === "fail" && <Icon name="x" className="text-fail" />}
              {r.status === "not_exercised" && <Icon name="dash" className="text-faint" />}
            </span>
            <span className="min-w-0">
              <span className="block">{names.get(r.assertion_id) ?? r.type}</span>
              <span className="block text-[13px] text-muted">{r.evidence}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Fold({ title, children, open = false }: { title: string; children: ReactNode; open?: boolean }) {
  return (
    <details className="group" open={open}>
      <summary className="flex cursor-pointer items-center gap-2 text-muted hover:text-ink">
        <Icon name="chevron" className="h-3 w-3 transition-transform group-open:rotate-90" /> {title}
      </summary>
      <div className="mt-3 pl-5">{children}</div>
    </details>
  );
}

/** Serial output, compiler output, warnings and run details. Nothing here is needed to read the verdict. */
export function LogsTab({ trace, report, warnings, deviceModel }: { trace: Trace | null; report: Report | null; warnings: string[]; deviceModel: Report["device_model"] }) {
  const llm = report?.llm;
  return (
    <div className="space-y-5 py-6">
      <Fold title={`Serial output${trace ? ` (${trace.serial_log.length})` : ""}`} open>
        <div className="max-h-[260px] overflow-auto rounded-md bg-raised p-3 font-mono text-[12px] leading-5">
          {!trace || trace.serial_log.length === 0 ? (
            <span className="text-faint">No output</span>
          ) : (
            trace.serial_log.slice(0, 400).map((l, i) => (
              <div key={i} className="flex gap-3 whitespace-pre">
                <span className="shrink-0 text-faint">{(l.t_ms / 1000).toFixed(3)}</span>
                <span>{l.text}</span>
              </div>
            ))
          )}
        </div>
      </Fold>
      {report?.compile_log && (
        <Fold title="Compiler output">
          <pre className="max-h-64 overflow-auto rounded-md bg-raised p-3 font-mono text-[12px] text-muted">{report.compile_log}</pre>
        </Fold>
      )}
      {warnings.length > 0 && (
        <Fold title={`Warnings (${warnings.length})`}>
          <ul className="space-y-2 text-[13px] text-muted">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Fold>
      )}
      {deviceModel && (
        <Fold title="What the agent understood">
          <p className="text-[13px] text-muted">{deviceModel.summary}</p>
          {deviceModel.risks.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[13px] text-muted">
              {deviceModel.risks.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </Fold>
      )}
      {llm && llm.calls > 0 && (
        <p className="num pt-2 text-faint">
          {llm.model}: {llm.calls} calls, {llm.repairs} repairs, {llm.prompt_tokens + llm.completion_tokens} tokens
        </p>
      )}
    </div>
  );
}
