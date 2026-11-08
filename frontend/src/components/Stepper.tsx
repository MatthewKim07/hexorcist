import { RunState, StepName } from "../useRun";

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
    <div aria-label="Progress">
      <ol className="grid grid-cols-5 gap-2" aria-label="Agent steps">
        {stages.map((s, i) => (
          <li key={s.label} aria-current={i === current ? "step" : undefined}>
            <div className={`h-0.5 rounded-full ${s.status === "done" ? "bg-accent" : s.status === "failed" ? "bg-fail" : s.status === "running" ? "pulse-soft bg-accent" : s.status === "skipped" ? "bg-line" : "bg-line"}`} />
            <div className={`mt-2 text-[12px] ${s.status === "pending" || s.status === "skipped" ? "text-faint" : s.status === "failed" ? "text-fail" : "text-ink"}`}>{s.label}</div>
          </li>
        ))}
      </ol>
      <p className="mt-6 text-[16px]" aria-live="polite">
        {line}
      </p>
      {total > 0 && (
        <p className="num mt-2 text-faint">
          Scenarios {done} / {total}
          {state.bugs.length > 0 && <span className="ml-4">Bugs {state.bugs.length}</span>}
        </p>
      )}
    </div>
  );
}
