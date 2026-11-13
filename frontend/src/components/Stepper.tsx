import { RunState, StepName } from "../useRun";
import { Lamp } from "./ui";

const STAGES: { label: string; steps: StepName[] }[] = [
  { label: "Understand", steps: ["write", "understand", "compile"] },
  { label: "Attack", steps: ["attack"] },
  { label: "Measure", steps: ["execute", "diagnose"] },
  { label: "Fix", steps: ["fix"] },
  { label: "Verify", steps: ["verify", "report"] },
];

type Stage = "pending" | "running" | "done" | "failed" | "skipped";

function stageStatus(state: RunState, steps: StepName[]): Stage {
  // "write" only exists in Build runs.
  const all = steps.filter((s) => s !== "write" || state.steps.write).map((s) => state.steps[s]?.status ?? "pending");
  if (all.includes("failed")) {
    return "failed";
  }
  if (all.includes("running")) {
    return "running";
  }
  const seen = all.filter((s) => s !== "pending");
  if (!seen.length) {
    return "pending";
  }
  if (seen.every((s) => s === "skipped")) {
    return "skipped";
  }
  // Part of the stage has finished and the next part has not started: it is still the current stage.
  return seen.length === all.length ? "done" : "running";
}

/** The five stages as a slim bar, one status line, and a scenario count. */
export function Stepper({ state, total }: { state: RunState; total: number }) {
  const stages = STAGES.map((s) => ({ ...s, status: stageStatus(state, s.steps) }));
  const current = stages.findIndex((s) => s.status === "running" || s.status === "pending");
  const running = Object.entries(state.steps).filter(([, s]) => s?.status === "running");
  const line = running.length ? running[running.length - 1][1]!.detail : state.guard && !state.guard.allowed ? "Input guard flagged this upload" : "Starting";
  const iterations = Object.keys(state.results).map(Number);
  const latest = iterations.length ? Math.max(...iterations) : 0;
  const done = Object.keys(state.results[latest] ?? {}).length;

  return (
    <div aria-label="Progress" className="screen rounded-xl border border-[#0b0f0e] bg-screen px-5 py-5 text-screen-ink shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]">
      <ol className="grid grid-cols-5 gap-2" aria-label="Agent steps">
        {stages.map((s, i) => (
          <li key={s.label} aria-current={i === current ? "step" : undefined} className="flex flex-col items-center gap-3 text-center">
            <Lamp tone={s.status === "failed" ? "fail" : s.status === "done" || s.status === "running" ? "trace" : "off"} breathing={s.status === "running"} />
            <span className={`text-xs ${s.status === "pending" || s.status === "skipped" ? "text-screen-muted" : s.status === "failed" ? "text-fail-lit" : "text-screen-ink"}`}>
              {s.label}
              <span className="sr-only">, {s.status}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-t border-screen-line pt-4">
        <p className="text-sm" aria-live="polite">
          {line}
        </p>
        {total > 0 && (
          <p className="num text-xs text-screen-muted">
            Scenarios {done} of {total}
            {state.bugs.length > 0 && <span className="ml-4">Bugs {state.bugs.length}</span>}
          </p>
        )}
      </div>
    </div>
  );
}
