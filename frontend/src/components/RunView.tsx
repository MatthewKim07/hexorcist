import { useEffect, useMemo, useRef, useState } from "react";
import { Bug, PinSpec, Report } from "../api";
import { useRun } from "../useRun";
import { Badge, DiffView, Icon, Panel, StatusBadge } from "./Common";
import { BugCards } from "./BugCards";
import { ComparePanel } from "./ComparePanel";
import { ContainedSummary, ContainmentPanel } from "./ContainmentPanel";
import { Replay } from "./Replay";
import { ScenarioGrid } from "./ScenarioGrid";
import { Timeline } from "./Timeline";

function headline(report: Report | null, status: string): { title: string; sub: string } {
  const s = report?.score;
  const n = s?.bugs_found ?? 0;
  const v = s?.bugs_verified ?? 0;
  const bugs = `${n} bug${n === 1 ? "" : "s"}`;
  switch (status) {
    case "fixed":
      return { title: `${bugs} cast out, ${v} verified`, sub: `Patch ${report?.fix?.iteration} passes all ${s?.scenarios} scenarios and ${s?.assertions} checks on the emulator, with no regressions.` };
    case "clean":
      return { title: "No possession detected", sub: `All ${s?.assertions} checks passed across ${s?.scenarios} attack scenarios.` };
    case "partial":
      return { title: `${bugs} found, ${v} verified`, sub: "The best patch still fails some checks or broke something else, so it is not claimed as a fix." };
    case "unfixed":
      return { title: `${bugs} found, no working fix`, sub: "The bugs below are real and measured. No patch passed verification." };
    case "inconclusive":
      return { title: "Inconclusive: the spec was not fully checked", sub: "Nothing failed, but this is not an all-clear. See the warnings below." };
    case "compile_failed":
      return { title: "It does not compile", sub: "These are the real compiler errors from the sandbox." };
    case "contained":
      return { title: `Contained: ${s?.checks_passed} of ${s?.checks_total} checks passed`, sub: "Guard flagged it, the LLM never saw it, and the sandbox held anyway." };
    case "containment_failed":
      return { title: "A containment check failed", sub: "Review the failed checks below." };
    case "blocked":
      return { title: "Blocked by the input guard", sub: "The LLM was not contacted." };
    case "interrupted":
      return { title: "This run was interrupted", sub: "The backend restarted while it was running." };
    case "error":
      return { title: "The run failed", sub: report?.error ?? "" };
    default:
      return { title: "Attacking the firmware…", sub: "Every result below comes from the real binary running on an emulated chip." };
  }
}

export function RunView({ runId }: { runId: string }) {
  const state = useRun(runId);
  const report = state.run?.report ?? null;
  const status = state.doneStatus ?? (state.run?.status === "running" ? "running" : state.run?.status) ?? "running";
  const pins: PinSpec[] = report?.spec?.pins ?? state.spec?.pins ?? state.run?.spec?.pins ?? [];
  const [gridIteration, setGridIteration] = useState(0);
  const [scenarioId, setScenarioId] = useState<string | null>(null);

  const scenarios = report?.scenarios?.length ? report.scenarios : state.scenarios;
  const emulated = useMemo(() => scenarios.filter((s) => !s.id.startsWith("containment-")), [scenarios]);
  const bugs = report?.bugs?.length ? report.bugs : state.bugs;

  useEffect(() => {
    if (report?.bugs?.length) {
      setScenarioId((cur) => cur ?? report.bugs[0].scenario_id);
    } else if (emulated.length) {
      setScenarioId((cur) => cur ?? emulated[0].id);
    }
  }, [report, emulated]);

  useEffect(() => {
    const iterations = Object.keys(state.results).map(Number);
    if (iterations.length) {
      setGridIteration(report?.fix?.iteration ?? Math.max(...iterations));
    }
  }, [state.results, report]);

  const replayTo = (id: string) => {
    setScenarioId(id);
    document.getElementById("replay")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Whether the run was already finished when this page opened. If so, nothing should look like it is running.
  const openedLive = useRef<boolean | null>(null);
  if (openedLive.current === null && state.run) {
    openedLive.current = state.run.status === "running";
  }
  const [understoodOpen, setUnderstoodOpen] = useState<boolean | null>(null);

  if (!state.run) {
    return (
      <div className="space-y-4" aria-busy="true">
        <div className="panel h-[104px] p-4">
          <div className="h-5 w-40 rounded bg-raised" />
          <div className="mt-4 h-7 w-72 rounded bg-raised" />
        </div>
      </div>
    );
  }

  const { title, sub } = headline(report, status);
  const meta = status === "running" ? "border-halo/40" : ["fixed", "clean", "contained"].includes(status) ? "border-pass/40" : ["error", "unfixed", "compile_failed", "containment_failed"].includes(status) ? "border-fail/40" : "border-warn/40";
  const guard = state.guard ?? state.run?.guard;
  const warnings = report?.warnings ?? state.warnings;
  const hasBoard = emulated.length > 0 && pins.length > 0;
  const comparable = state.run?.mode === "break" && !!guard?.allowed && ["fixed", "partial", "unfixed", "clean", "inconclusive"].includes(status);

  return (
    <div className="space-y-4">
      <div className={`panel ${meta} p-4`}>
        <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
          <StatusBadge status={status} />
          <span className="font-mono">{state.run?.mode === "build" ? "build" : "break"} / {runId}</span>
          <span>{state.run?.title}</span>
          {state.connectionLost && status === "running" && <Badge tone="warn" icon="warn">Reconnecting…</Badge>}
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{title}</h1>
        {sub && <p className="mt-0.5 text-muted">{sub}</p>}
        {report && ["fixed", "partial", "unfixed"].includes(status) && bugs.length > 0 && <Glance bugs={bugs} />}
        {report?.llm && report.llm.calls > 0 && (
          <p className="mt-2 font-mono text-[11px] text-faint">
            {report.llm.model}: {report.llm.calls} calls, {report.llm.repairs} JSON repairs, {report.llm.prompt_tokens + report.llm.completion_tokens} tokens
          </p>
        )}
      </div>

      {report?.contained && <ContainedSummary report={report} />}

      <Timeline state={state} />

      {state.run.mode === "break" && status !== "running" && hasBoard && <JumpNav hasBugs={bugs.length > 0} hasFix={!!report?.fix} hasCompare={comparable} />}

      {guard && !guard.allowed && (
        <div className="panel border-warn/40 bg-warn/5 p-4">
          <div className="flex items-center gap-2 font-medium">
            <Icon name="shield" className="text-warn" /> Input guard flagged this upload <Badge tone="warn">score {guard.score}</Badge>
            <span className="text-[12px] font-normal text-muted">{guard.reasons.length} reasons</span>
          </div>
          <ul className="mt-2 space-y-0.5 text-[13px] text-muted">
            {guard.reasons.slice(0, 3).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {guard.reasons.length > 3 && (
            <details className="mt-1 text-[13px]">
              <summary className="cursor-pointer text-muted hover:text-ink">and {guard.reasons.length - 3} more</summary>
              <ul className="mt-1 space-y-0.5 text-muted">
                {guard.reasons.slice(3).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {warnings.length > 0 && (
        <details className="panel px-4 py-2.5 text-[13px]" open={status === "inconclusive"}>
          <summary className="cursor-pointer text-warn">{warnings.length} warning{warnings.length === 1 ? "" : "s"} from this run</summary>
          <ul className="mt-2 space-y-1 text-muted">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      )}

      {report?.compile_log && status === "compile_failed" && (
        <Panel title="Compiler output">
          <pre className="max-h-96 overflow-auto p-4 font-mono text-[12px] text-muted">{report.compile_log}</pre>
        </Panel>
      )}

      {(state.deviceModel || state.assertions.length > 0) && (
        <details className="panel px-4 py-2.5" open={understoodOpen ?? !!openedLive.current} onToggle={(e) => setUnderstoodOpen((e.currentTarget as HTMLDetailsElement).open)}>
          <summary className="panel-title cursor-pointer">What the agent understood: {state.assertions.length} checks</summary>
          {state.deviceModel?.summary && <p className="mt-2 text-[13px]">{state.deviceModel.summary}</p>}
          {!!state.deviceModel?.risks?.length && (
            <ul className="mt-1 list-disc pl-4 text-[13px] text-muted">
              {state.deviceModel.risks.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
          <ul className="mt-2 grid gap-1 md:grid-cols-2">
            {state.assertions.map((a) => (
              <li key={a.id} className="flex gap-2 text-[12.5px]">
                <span className="shrink-0"><Badge>{a.type}</Badge></span>
                <span className="text-muted">{a.description}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {scenarios.length > 0 && <ScenarioGrid state={{ ...state, scenarios }} iteration={gridIteration} onIteration={setGridIteration} selected={scenarioId} onSelect={replayTo} />}

      {hasBoard && (
        <div id="replay" className="scroll-mt-16">
          <Replay runId={runId} pins={pins} scenarios={emulated} assertions={report?.assertions ?? state.assertions} scenarioId={scenarioId} onScenario={setScenarioId} report={report} iterationReady={(n, id) => !!state.results[n]?.[id]} />
        </div>
      )}

      {bugs.length > 0 && (
        <div id="bugs" className="scroll-mt-16">
          <BugCards bugs={bugs} report={report} onReplay={replayTo} />
        </div>
      )}

      {comparable && (
        <div id="compare" className="scroll-mt-16">
          <ComparePanel runId={runId} bugs={bugs} report={report} finished />
        </div>
      )}

      {report?.fix && (
        <Panel id="patch" className="scroll-mt-16" title={`The patch: ${report.fix.diff.added} lines added, ${report.fix.diff.removed} removed`}>
          <div className="space-y-2 p-4">
            {report.fix.summary && <p className="text-[13px]">{report.fix.summary}</p>}
            <DiffView unified={report.fix.diff.unified} />
          </div>
        </Panel>
      )}

      <div id="containment" className="scroll-mt-16">
        <ContainmentPanel records={report?.containment?.records ?? state.records} report={report} />
      </div>
    </div>
  );
}

function Glance({ bugs }: { bugs: Bug[] }) {
  return (
    <div className="mt-3 grid gap-2 md:grid-cols-2" aria-label="Measured evidence at a glance">
      {bugs.slice(0, 4).map((bug) => (
        <div key={bug.id} className="rounded-md border border-line bg-raised/60 p-3">
          <div className="text-[13px] font-medium leading-snug">{bug.title}</div>
          <dl className="mt-1.5 grid grid-cols-[48px_minmax(0,1fr)] gap-x-2 gap-y-1 text-[12.5px] leading-snug">
            <dt className="font-mono text-fail">before</dt>
            <dd className="line-clamp-2">{bug.before?.evidence ?? bug.evidence}</dd>
            <dt className="font-mono text-pass">after</dt>
            <dd className="line-clamp-2 text-muted">{bug.after?.status === "pass" ? bug.after.evidence : "no verified fix"}</dd>
          </dl>
        </div>
      ))}
    </div>
  );
}

function JumpNav({ hasBugs, hasFix, hasCompare }: { hasBugs: boolean; hasFix: boolean; hasCompare: boolean }) {
  const go = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const items = [
    ["replay", "Board replay", true],
    ["bugs", "Bug report", hasBugs],
    ["compare", "LLM vs Hexorcist", hasCompare],
    ["patch", "Patch", hasFix],
    ["containment", "Containment", true],
  ] as const;
  return (
    <nav className="flex flex-wrap items-center gap-1.5" aria-label="Jump to a section">
      <span className="mr-1 text-[12px] text-faint">Jump to</span>
      {items.filter(([, , show]) => show).map(([id, label]) => (
        <button key={id} className="btn-ghost py-1 text-[12px]" onClick={() => go(id)}>
          {label}
        </button>
      ))}
    </nav>
  );
}
