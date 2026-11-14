import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Box, Bug, CircleCheck, CircleHelp, CircleX, Clock, Loader2, LucideIcon, ShieldCheck, Wand2, WifiOff } from "lucide-react";
import { Bug as BugType, PinSpec } from "../api";
import { displayTitle, keyFact, rankBugs, shortDuration } from "../format";
import { iconCardProps, iconProps } from "../icons";
import { runIcon } from "../presetIcons";
import { useRun } from "../useRun";
import { useTrace } from "../useTrace";
import { StageChip } from "./BoardStage";
import { BugList } from "./BugList";
import { ComparePanel } from "./ComparePanel";
import { STATUS_META, Tone, TONE_TEXT } from "./Common";
import { ContainmentDetails } from "./ContainmentPanel";
import { ChecksTab, LogsTab, ScenariosTab } from "./Details";
import { Replay } from "./Replay";
import { ReportTabs, ReportTabId } from "./ReportTabs";
import { ReportVerdict } from "./ReportVerdict";
import { RunPipeline } from "./RunPipeline";
import { Fold, reducedMotion } from "./ui";

/** The board opens paused this far ahead of the first failure, so pressing play shows it happen. */
const LEAD_MS = 300;

function headerStatus(status: string): { label: string; tone: Tone; Icon: LucideIcon; spin?: boolean } {
  switch (status) {
    case "running":
      return { label: "Running", tone: "neutral", Icon: Loader2, spin: true };
    case "fixed":
      return { label: "Fixed", tone: "pass", Icon: CircleCheck };
    case "clean":
      return { label: "Clean", tone: "pass", Icon: CircleCheck };
    case "contained":
      return { label: "Contained", tone: "pass", Icon: ShieldCheck };
    case "inconclusive":
      return { label: "Inconclusive", tone: "neutral", Icon: CircleHelp };
    default:
      return { label: STATUS_META[status]?.label ?? "Failed", tone: STATUS_META[status]?.tone ?? "fail", Icon: CircleX };
  }
}

function useElapsed(createdAt: number | undefined, finishedAt: number | null | undefined, running: boolean): string {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!running) {
      return;
    }
    const id = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, [running]);
  if (createdAt === undefined) {
    return "—";
  }
  return shortDuration(createdAt, finishedAt ?? (running ? now : createdAt)) || "0s";
}

function Skeleton() {
  return (
    <div aria-busy="true" className="space-y-6">
      <div className="h-4 w-24 rounded bg-[#FAFAFA]" />
      <div className="h-24 rounded-lg border border-line bg-[#FAFAFA]" />
      <div className="h-48 rounded-lg border border-line bg-[#FAFAFA]" />
    </div>
  );
}

function RunHeader({ title, mode, status, createdAt, finishedAt, sandboxCount, connectionLost }: { title: string; mode: string; status: string; createdAt: number; finishedAt: number | null; sandboxCount: number; connectionLost: boolean }) {
  const running = status === "running";
  const elapsed = useElapsed(createdAt, finishedAt, running);
  const Device = runIcon(title, mode);
  const st = headerStatus(status);
  const ModeIcon = mode === "build" ? Wand2 : Bug;
  const modeLabel = mode === "build" ? "Write firmware" : "Find bugs";
  const color = status === "running" ? "text-running" : TONE_TEXT[st.tone];

  return (
    <div className="border border-line bg-white p-5" style={{ borderRadius: 8 }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line bg-[#FAFAFA] text-ink">
            <Device {...iconCardProps} />
          </span>
          <h1 className="truncate text-lg font-semibold tracking-tight text-ink">{displayTitle(title)}</h1>
        </div>
        <span className={`inline-flex shrink-0 items-center gap-2 text-sm ${color}`}>
          <st.Icon {...iconProps} className={st.spin ? "animate-spin" : ""} />
          {st.label}
        </span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Clock {...iconProps} />
          {elapsed}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <ModeIcon {...iconProps} />
          {modeLabel}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Box {...iconProps} />
          {sandboxCount} sandbox{sandboxCount === 1 ? "" : "es"}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <WifiOff {...iconProps} />
          no network
        </span>
        {connectionLost && running && <span className="text-running">Reconnecting</span>}
      </div>
    </div>
  );
}

/** Finished-run report: verdict, replay, bugs, patch, detail tabs. */
function FinishedReport({ runId, state, status }: { runId: string; state: ReturnType<typeof useRun>; status: string }) {
  const report = state.run?.report ?? null;
  const pins: PinSpec[] = report?.spec?.pins ?? state.spec?.pins ?? state.run?.spec?.pins ?? [];
  const [chosenId, setScenarioId] = useState<string | null>(null);
  const [side, setSide] = useState<"before" | "after">("before");
  const [tab, setTab] = useState<ReportTabId | null>(null);
  const [openBug, setOpenBug] = useState<string | null>(null);

  const scenarios = report?.scenarios?.length ? report.scenarios : state.scenarios;
  const emulated = useMemo(() => scenarios.filter((s) => !s.id.startsWith("containment-")), [scenarios]);
  const bugs = useMemo(() => rankBugs(report?.bugs?.length ? report.bugs : state.bugs), [report, state.bugs]);
  const afterIteration = report?.fix?.iteration ?? null;
  const iteration = side === "after" && afterIteration !== null ? afterIteration : 0;
  const scenarioId = chosenId ?? (report ? (bugs[0]?.scenario_id ?? emulated[0]?.id ?? null) : null);
  const ready = !!scenarioId && !!state.results[iteration]?.[scenarioId];
  const { trace, error: traceError } = useTrace(runId, iteration, scenarioId, ready);
  const results = useMemo(() => report?.matrix?.[String(iteration)]?.[scenarioId ?? ""] ?? [], [report, iteration, scenarioId]);
  const violations = useMemo(() => results.filter((r) => r.status === "fail").flatMap((r) => r.violations), [results]);
  const startAt = useMemo(() => {
    const failing = (report?.matrix?.["0"]?.[scenarioId ?? ""] ?? []).filter((r) => r.status === "fail");
    const bug = bugs.find((b) => b.scenario_id === scenarioId);
    const own = failing.filter((r) => r.assertion_id === bug?.assertion_id);
    const first = (own.length ? own : failing).flatMap((r) => r.violations).sort((a, b) => a.t_start - b.t_start)[0];
    if (first && first.t_start < LEAD_MS) {
      return Math.ceil(first.t_end / 100) * 100;
    }
    const anchor = first?.t_start ?? trace?.pin_events.find((e) => e.dir === "out")?.t_ms;
    if (anchor === undefined) {
      return trace ? 0 : null;
    }
    return Math.max(0, Math.floor((anchor - LEAD_MS) / 100) * 100);
  }, [report, bugs, scenarioId, trace]);

  const assertions = report?.assertions ?? state.assertions;
  const chips: StageChip[] = useMemo(
    () =>
      assertions.flatMap((a) => {
        const r = results.find((x) => x.assertion_id === a.id);
        if (a.type === "no_crash" && r?.status !== "fail") {
          return [];
        }
        const tone = r?.status === "fail" ? "fail" : r?.status === "pass" ? "pass" : "off";
        return [{ key: a.id, check: a, tone, status: tone === "fail" ? "broken in this scenario" : tone === "pass" ? "held in this scenario" : "not measured in this scenario" }];
      }),
    [assertions, results],
  );

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

  const guard = state.guard ?? state.run!.guard;
  const warnings = report?.warnings ?? state.warnings;
  const hasBoard = emulated.length > 0 && pins.length > 0;
  const comparable = state.run!.mode === "break" && !!guard?.allowed && ["fixed", "partial", "unfixed", "clean", "inconclusive"].includes(status);
  const records = report?.containment?.records ?? state.records;
  const focus = bugs.find((b) => b.scenario_id === scenarioId) ?? null;
  const scenario = scenarios.find((s) => s.id === scenarioId);
  const evidence = focus ? { before: keyFact(focus.before?.evidence ?? focus.evidence), after: focus.after?.status === "pass" ? keyFact(focus.after.evidence) : "" } : null;
  const beforeResults = state.results[0] ?? {};
  const afterResults = afterIteration !== null ? (state.results[afterIteration] ?? {}) : null;
  const beforeMatrix = report?.matrix?.["0"];
  const afterMatrix = afterIteration !== null ? report?.matrix?.[String(afterIteration)] : undefined;
  const contained = !!report?.contained;

  const tabs: ReportTabId[] = [];
  if (hasBoard) {
    tabs.push("scenarios", "checks");
  }
  if (records.length && !contained) {
    tabs.push("containment");
  }
  if (comparable) {
    tabs.push("compare");
  }
  if (report && !contained) {
    tabs.push("logs");
  }
  const activeTab = tab && tabs.includes(tab) ? tab : tabs[0] ?? null;

  const onFocus = (bug: BugType) => {
    setScenarioId(bug.scenario_id);
    showReplay();
  };
  const onChip = (chip: StageChip) => {
    const bug = bugs.find((b) => b.assertion_id === chip.key && b.scenario_id === scenarioId) ?? bugs.find((b) => b.assertion_id === chip.key);
    if (chip.tone === "fail" && bug) {
      setOpenBug(bug.id);
      requestAnimationFrame(() => document.getElementById(`bug-${bug.id}`)?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "center" }));
    } else {
      setTab("checks");
    }
  };
  const activeChip = bugs.find((b) => b.id === openBug)?.assertion_id ?? null;

  return (
    <div className="space-y-8">
      <ReportVerdict report={report} status={status} firstWarning={warnings[0] ?? ""} createdAt={state.run!.created_at} finishedAt={state.run!.finished_at} />

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

      {status === "compile_failed" && report?.compile_log && <pre className="scroll max-h-96 overflow-auto rounded-md border border-line bg-[#FAFAFA] p-4 font-mono text-xs text-muted">{report.compile_log}</pre>}

      {contained && records.length > 0 && <ContainmentDetails records={records} report={report} guard={guard} inline />}

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
          startAt={startAt}
          chips={report ? chips : undefined}
          onChip={onChip}
          activeChip={activeChip}
        />
      )}

      {!contained && bugs.length > 0 && <BugList bugs={bugs} report={report} assertions={assertions} pins={pins} focusId={focus?.id ?? null} onFocus={onFocus} open={openBug} onOpen={setOpenBug} />}

      {tabs.length > 0 && (
        <ReportTabs tabs={tabs} value={activeTab} onChange={setTab}>
          {activeTab === "scenarios" && (
            <ScenariosTab
              scenarios={emulated}
              beforeResults={beforeResults}
              afterResults={afterResults}
              beforeMatrix={beforeMatrix}
              afterMatrix={afterMatrix}
              assertions={assertions}
              pins={pins}
              selected={scenarioId}
              onSelect={replayTo}
            />
          )}
          {activeTab === "checks" && <ChecksTab results={results} assertions={report?.assertions ?? state.assertions} scenarioName={scenario?.name ?? ""} side={side} />}
          {activeTab === "containment" && <ContainmentDetails records={records} report={report} guard={guard} />}
          {activeTab === "compare" && comparable && <ComparePanel runId={runId} bugs={bugs} report={report} finished />}
          {activeTab === "logs" && <LogsTab trace={trace} report={report} warnings={warnings} deviceModel={report?.device_model ?? state.deviceModel} />}
        </ReportTabs>
      )}
    </div>
  );
}

export function RunView({ runId }: { runId: string }) {
  const state = useRun(runId);
  const status = state.doneStatus ?? (state.run?.status === "running" ? "running" : state.run?.status) ?? "running";
  const running = status === "running";
  const sandboxCount = (state.run?.report?.containment?.records ?? state.records).length;

  if (state.notFound) {
    return (
      <div>
        <a href="#/runs" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-ink">
          <ArrowLeft {...iconProps} />
          Runs
        </a>
        <p className="mt-8 text-sm text-muted">
          That run was not found.{" "}
          <a href="#/runs" className="text-ink underline-offset-2 hover:underline">
            Back to Runs
          </a>
          .
        </p>
      </div>
    );
  }

  if (state.loadError && !state.run) {
    return (
      <div>
        <a href="#/runs" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-ink">
          <ArrowLeft {...iconProps} />
          Runs
        </a>
        <p className="mt-8 text-sm text-fail">Could not load this run.</p>
      </div>
    );
  }

  if (!state.run) {
    return <Skeleton />;
  }

  return (
    <div className="space-y-6">
      <a href="#/runs" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-ink">
        <ArrowLeft {...iconProps} />
        Runs
      </a>

      <RunHeader
        title={state.run.title}
        mode={state.run.mode}
        status={status}
        createdAt={state.run.created_at}
        finishedAt={state.run.finished_at}
        sandboxCount={sandboxCount}
        connectionLost={state.connectionLost}
      />

      {running && <RunPipeline state={state} finished={false} />}

      {!running && <FinishedReport runId={runId} state={state} status={status} />}

      {!running && <RunPipeline state={state} finished />}
    </div>
  );
}
