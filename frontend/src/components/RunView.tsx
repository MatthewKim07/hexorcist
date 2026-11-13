import { useEffect, useMemo, useState } from "react";
import { Bug, PinSpec, Report } from "../api";
import { duration, keyFact, rankBugs } from "../format";
import { useRun } from "../useRun";
import { useTrace } from "../useTrace";
import { BugList } from "./BugList";
import { ComparePanel } from "./ComparePanel";
import { Icon, STATUS_META, TONE_TEXT } from "./Common";
import { ContainedRow, ContainmentDetails } from "./ContainmentPanel";
import { ChecksTab, LogsTab, ScenariosTab } from "./Details";
import { Replay } from "./Replay";
import { Stepper } from "./Stepper";
import { Fold, TabStrip, Ticking } from "./ui";

type TabId = "scenarios" | "checks" | "containment" | "compare" | "logs";

function headline(report: Report | null, status: string, firstWarning: string): { title: string; sub: string } {
  const s = report?.score;
  const n = s?.bugs_found ?? 0;
  const v = s?.bugs_verified ?? 0;
  const bugs = `${n} bug${n === 1 ? "" : "s"} found`;
  const fixed = v === n ? (n === 1 ? "fixed and verified" : n === 2 ? "both fixed and verified" : "all fixed and verified") : `${v} fixed and verified`;
  switch (status) {
    case "fixed":
      return { title: `${bugs}, ${fixed}`, sub: "" };
    case "clean":
      return { title: "No bugs found", sub: `${s?.assertions} checks passed in ${s?.scenarios} scenarios` };
    case "partial":
      return { title: `${bugs}, ${v} fixed and verified`, sub: "The best patch still fails a check, so it is not claimed as a fix" };
    case "unfixed":
      return { title: `${bugs}, no working fix`, sub: "" };
    case "inconclusive":
      return { title: "Inconclusive", sub: firstWarning || "Not everything could be checked" };
    case "compile_failed":
      return { title: "Does not compile", sub: "" };
    case "contained":
      return { title: "Contained", sub: `${s?.checks_passed} of ${s?.checks_total} checks passed` };
    case "containment_failed":
      return { title: "Not contained", sub: "A containment check failed" };
    case "blocked":
      return { title: "Blocked by the input guard", sub: "No LLM call was made" };
    case "interrupted":
      return { title: "Interrupted", sub: "The backend restarted during the run" };
    case "error":
      return { title: "The run failed", sub: report?.error ?? "" };
    default:
      return { title: "", sub: "" };
  }
}

function Skeleton() {
  return (
    <div aria-busy="true" className="space-y-6">
      <div className="h-4 w-40 rounded bg-raised" />
      <div className="h-[34px] w-80 rounded bg-raised" />
    </div>
  );
}

export function RunView({ runId }: { runId: string }) {
  const state = useRun(runId);
  const report = state.run?.report ?? null;
  const status = state.doneStatus ?? (state.run?.status === "running" ? "running" : state.run?.status) ?? "running";
  const pins: PinSpec[] = report?.spec?.pins ?? state.spec?.pins ?? state.run?.spec?.pins ?? [];
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [side, setSide] = useState<"before" | "after">("before");
  const [tab, setTab] = useState<TabId | null>(null);

  const scenarios = report?.scenarios?.length ? report.scenarios : state.scenarios;
  const emulated = useMemo(() => scenarios.filter((s) => !s.id.startsWith("containment-")), [scenarios]);
  const bugs = useMemo(() => rankBugs(report?.bugs?.length ? report.bugs : state.bugs), [report, state.bugs]);
  const afterIteration = report?.fix?.iteration ?? null;
  const iteration = side === "after" && afterIteration !== null ? afterIteration : 0;

  useEffect(() => {
    // Wait for the report on a finished run, so the board opens on the worst bug and not on the first scenario.
    if (!report) {
      return;
    }
    if (bugs.length) {
      setScenarioId((cur) => cur ?? bugs[0].scenario_id);
    } else if (emulated.length) {
      setScenarioId((cur) => cur ?? emulated[0].id);
    }
  }, [report, bugs, emulated]);

  const ready = !!scenarioId && !!state.results[iteration]?.[scenarioId];
  const { trace, error: traceError } = useTrace(runId, iteration, scenarioId, ready);
  const results = useMemo(() => report?.matrix?.[String(iteration)]?.[scenarioId ?? ""] ?? [], [report, iteration, scenarioId]);
  const violations = useMemo(() => results.filter((r) => r.status === "fail").flatMap((r) => r.violations), [results]);

  const showReplay = () => {
    const el = document.getElementById("replay");
    if (el && el.getBoundingClientRect().top < 56) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };
  const replayTo = (id: string) => {
    setScenarioId(id);
    showReplay();
  };

  if (!state.run) {
    return <Skeleton />;
  }

  const running = status === "running";
  const guard = state.guard ?? state.run.guard;
  const warnings = report?.warnings ?? state.warnings;
  const { title, sub } = headline(report, status, warnings[0] ?? "");
  const meta = STATUS_META[status] ?? { tone: "neutral" as const };
  const hasBoard = !running && emulated.length > 0 && pins.length > 0;
  const comparable = state.run.mode === "break" && !!guard?.allowed && ["fixed", "partial", "unfixed", "clean", "inconclusive"].includes(status);
  const records = report?.containment?.records ?? state.records;
  const focus = bugs.find((b) => b.scenario_id === scenarioId) ?? null;
  const scenario = scenarios.find((s) => s.id === scenarioId);
  const evidence = focus ? { before: keyFact(focus.before?.evidence ?? focus.evidence), after: focus.after?.status === "pass" ? keyFact(focus.after.evidence) : "" } : null;
  const emulatedResults = state.results[iteration] ?? {};

  const tabs: { value: TabId; label: string }[] = [];
  if (!running) {
    if (hasBoard) {
      tabs.push({ value: "scenarios", label: "Scenarios" }, { value: "checks", label: "Checks" });
    }
    if (records.length) {
      tabs.push({ value: "containment", label: "Containment" });
    }
    if (comparable) {
      tabs.push({ value: "compare", label: "Compare with plain LLM" });
    }
    if (report && !report.contained) {
      tabs.push({ value: "logs", label: "Logs" });
    }
  }

  const onFocus = (bug: Bug) => {
    setScenarioId(bug.scenario_id);
    showReplay();
  };

  return (
    <div className="space-y-8">
      <header>
        <p className="label flex flex-wrap items-baseline justify-between gap-x-6">
          <span>
            {state.run.title}
            {report && state.run.mode === "build" && <span>, built from a description</span>}
          </span>
          {state.run.finished_at && <span className="num">{duration(state.run.created_at, state.run.finished_at)}</span>}
          {state.connectionLost && running && <span>Reconnecting</span>}
        </p>
        {running ? (
          <div className="mt-6">
            <Stepper state={state} total={emulated.length} />
          </div>
        ) : (
          <>
            <h1 className="headline mt-2 flex items-center gap-3">
              {meta.tone !== "neutral" && <Icon name={meta.tone === "pass" ? "check" : "x"} className={`h-6 w-6 shrink-0 ${TONE_TEXT[meta.tone]}`} />}
              {title}
            </h1>
            {sub && <Ticking className="mt-2 block text-base text-muted" text={sub} />}
          </>
        )}
      </header>

      {report?.contained && <ContainedRow report={report} />}

      {status === "blocked" && guard && !guard.allowed && (
        <section aria-label="Guard reasons">
          <ul className="space-y-2 text-muted">
            {guard.reasons.slice(0, 3).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {guard.reasons.length > 3 && (
            <Fold className="mt-3" title={`${guard.reasons.length - 3} more`}>
              <ul className="space-y-2 text-muted">
                {guard.reasons.slice(3).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </Fold>
          )}
        </section>
      )}

      {status === "compile_failed" && report?.compile_log && <pre className="scroll max-h-96 overflow-auto rounded-md border border-line bg-raised p-4 font-mono text-xs text-muted">{report.compile_log}</pre>}

      {hasBoard && (
        <Replay
          pins={pins}
          scenarios={emulated}
          scenarioId={scenarioId}
          onScenario={setScenarioId}
          trace={trace}
          error={traceError}
          ready={ready}
          side={side}
          onSide={setSide}
          hasAfter={afterIteration !== null}
          violations={violations}
          evidence={evidence}
        />
      )}

      {!running && bugs.length > 0 && <BugList bugs={bugs} report={report} focusId={focus?.id ?? null} onFocus={onFocus} />}

      {tabs.length > 0 && (
        <section>
          <TabStrip label="Details" closable tabs={tabs} value={tab} onChange={setTab}>
          {tab === "scenarios" && <ScenariosTab scenarios={emulated} results={emulatedResults} selected={scenarioId} onSelect={replayTo} />}
          {tab === "checks" && <ChecksTab results={results} assertions={report?.assertions ?? state.assertions} scenarioName={scenario?.name ?? ""} side={side} />}
          {tab === "containment" && <ContainmentDetails records={records} report={report} guard={guard} />}
          {tab === "compare" && comparable && <ComparePanel runId={runId} bugs={bugs} report={report} finished />}
          {tab === "logs" && <LogsTab trace={trace} report={report} warnings={warnings} deviceModel={report?.device_model ?? state.deviceModel} />}
          </TabStrip>
        </section>
      )}
    </div>
  );
}
