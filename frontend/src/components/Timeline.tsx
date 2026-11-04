import { RunState, StepName, STEP_ORDER } from "../useRun";
import { Icon, STATUS_META } from "./Common";

const LABELS: Record<StepName, string> = {
  write: "Write",
  understand: "Understand",
  compile: "Compile",
  attack: "Attack plan",
  execute: "Execute",
  diagnose: "Diagnose",
  fix: "Fix",
  verify: "Verify",
  report: "Report",
};

export function Timeline({ state }: { state: RunState }) {
  const steps = STEP_ORDER.filter((s) => s !== "write" || state.steps.write);
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-flow-col lg:auto-cols-fr lg:grid-cols-none" aria-label="Agent steps">
      {steps.map((name) => {
        const step = state.steps[name];
        const status = step?.status ?? "pending";
        const elapsed = step?.startedAt && step?.endedAt ? step.endedAt - step.startedAt : null;
        const tone =
          status === "running" ? "border-halo/70 shadow-halo" : status === "done" ? "border-pass/30" : status === "failed" ? "border-fail/50" : "border-line";
        return (
          <li key={name} className={`min-w-0 rounded-lg border bg-panel p-2.5 transition-colors ${tone}`} title={step?.detail}>
            <div className="flex items-center gap-1.5 text-[12px] font-medium">
              {status === "running" && <span className="spin inline-block h-3 w-3 rounded-full border-2 border-halo border-t-transparent" aria-label="running" />}
              {status === "done" && <Icon name="check" className="text-pass" />}
              {status === "failed" && <Icon name="x" className="text-fail" />}
              {status === "skipped" && <Icon name="dash" className="text-faint" />}
              {status === "pending" && <Icon name="dot" className="text-line" />}
              <span className={status === "pending" || status === "skipped" ? "text-faint" : "text-ink"}>{LABELS[name]}</span>
              {elapsed !== null && elapsed >= 0.1 && <span className="ml-auto font-mono text-[10px] text-faint">{elapsed.toFixed(1)}s</span>}
            </div>
            <p className="mt-1 line-clamp-3 min-h-[3.2em] text-[11px] leading-snug text-muted">{name === "report" && step ? STATUS_META[step.detail]?.label ?? step.detail : step?.detail ?? ""}</p>
          </li>
        );
      })}
    </ol>
  );
}
