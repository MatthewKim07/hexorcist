import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Circle, CircleCheck, CircleX, Loader2 } from "lucide-react";
import { shortDuration } from "../format";
import { iconProps } from "../icons";
import { RunState, STEP_LABELS, STEP_ORDER, StepName, StepState } from "../useRun";

function stepList(mode: string, steps: RunState["steps"], finished: boolean): StepName[] {
  const order = (mode === "build" ? [...STEP_ORDER] : STEP_ORDER.filter((s) => s !== "write")) as StepName[];
  if (finished) {
    return order.filter((s) => steps[s]);
  }
  return order;
}

function statusOf(step: StepState | undefined): StepState["status"] {
  return step?.status ?? "pending";
}

function StatusIcon({ status }: { status: StepState["status"] }) {
  if (status === "running") {
    return <Loader2 {...iconProps} className="shrink-0 animate-spin text-running" />;
  }
  if (status === "done") {
    return <CircleCheck {...iconProps} className="shrink-0 text-pass" />;
  }
  if (status === "failed") {
    return <CircleX {...iconProps} className="shrink-0 text-fail" />;
  }
  if (status === "skipped") {
    return <Check {...iconProps} className="shrink-0 text-muted opacity-40" />;
  }
  return <Circle {...iconProps} className="shrink-0 text-muted" />;
}

function LogPanel({ lines }: { lines: string[] }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines]);
  if (!lines.length) {
    return null;
  }
  return (
    <div ref={box} className="scroll mt-2 max-h-[calc(13px*1.5*10)] overflow-y-auto rounded-md border border-line bg-[#FAFAFA] px-3 py-2 font-mono text-[13px] leading-[1.5] text-muted">
      {lines.map((line, i) => (
        <div key={`${i}-${line.slice(0, 24)}`} className="whitespace-pre-wrap break-words">
          {line}
        </div>
      ))}
    </div>
  );
}

function executeProgress(state: RunState): string {
  const total = state.scenarios.filter((s) => !s.id.startsWith("containment-")).length;
  if (!total) {
    return "";
  }
  const iterations = Object.keys(state.results).map(Number);
  const latest = iterations.length ? Math.max(...iterations) : 0;
  const done = Object.keys(state.results[latest] ?? {}).filter((id) => !id.startsWith("containment-")).length;
  return `${done} / ${total} scenarios`;
}

function stepDuration(step: StepState | undefined, nowSec: number): string {
  if (!step?.startedAt) {
    return "";
  }
  const end = step.endedAt ?? (step.status === "running" ? nowSec : null);
  if (end === null) {
    return "";
  }
  return shortDuration(step.startedAt, end);
}

/** Vercel build-log style vertical step list for a live or finished run. */
export function RunPipeline({ state, finished }: { state: RunState; finished: boolean }) {
  const mode = state.run?.mode ?? "break";
  const names = stepList(mode, state.steps, finished);
  const runningName = names.find((n) => state.steps[n]?.status === "running") ?? null;
  const [open, setOpen] = useState<StepName | null>(null);
  const [now, setNow] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (finished) {
      setOpen(null);
      return;
    }
    if (runningName) {
      setOpen(runningName);
    }
  }, [runningName, finished]);

  useEffect(() => {
    if (finished) {
      return;
    }
    const id = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, [finished]);

  if (!names.length) {
    return null;
  }

  return (
    <ol className="divide-y divide-line border border-line" style={{ borderRadius: 8 }}>
      {names.map((name) => {
        const step = state.steps[name];
        const status = statusOf(step);
        const expanded = open === name && (status === "running" || status === "done" || status === "failed" || status === "skipped");
        const progress = name === "execute" && status === "running" ? executeProgress(state) : "";
        const canToggle = status === "done" || status === "failed" || status === "skipped";
        const dur = stepDuration(step, now);
        return (
          <li key={name} className="px-4 py-3">
            <button
              type="button"
              className={`flex w-full items-center gap-3 text-left text-sm ${canToggle ? "cursor-pointer" : "cursor-default"}`}
              disabled={!canToggle}
              onClick={() => canToggle && setOpen((cur) => (cur === name ? null : name))}
              aria-expanded={expanded}
            >
              <StatusIcon status={status} />
              <span className={`min-w-0 flex-1 truncate ${status === "pending" ? "text-muted" : "text-ink"}`}>
                {STEP_LABELS[name]}
                {progress && <span className="ml-2 font-mono text-xs text-muted">{progress}</span>}
              </span>
              {dur && <span className="num shrink-0 text-xs text-muted">{dur}</span>}
              {canToggle && <ChevronDown {...iconProps} className={`shrink-0 text-muted transition-transform ${expanded ? "rotate-180" : ""}`} />}
            </button>
            {expanded && <LogPanel lines={step?.logs ?? (step?.detail ? [step.detail] : [])} />}
          </li>
        );
      })}
    </ol>
  );
}
