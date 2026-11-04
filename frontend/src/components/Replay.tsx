import { useEffect, useMemo, useRef, useState } from "react";
import { api, AssertionDef, AssertionResult, PinSpec, Report, Scenario, Trace, Violation } from "../api";
import { fmtTime } from "../trace";
import { Badge, Icon, Panel } from "./Common";
import { TraceChart } from "./TraceChart";
import { VirtualBoard } from "./VirtualBoard";

interface Props {
  runId: string;
  pins: PinSpec[];
  scenarios: Scenario[];
  assertions: AssertionDef[];
  scenarioId: string | null;
  onScenario: (id: string) => void;
  report: Report | null;
  iterationReady: (iteration: number, scenario: string) => boolean;
}

const SPEEDS = [0.25, 0.5, 1, 2, 4];

export function Replay({ runId, pins, scenarios, assertions, scenarioId, onScenario, report, iterationReady }: Props) {
  const afterIteration = report?.fix?.iteration ?? null;
  const [side, setSide] = useState<"before" | "after">("before");
  const iteration = side === "after" && afterIteration !== null ? afterIteration : 0;
  const [cache, setCache] = useState<Record<string, Trace>>({});
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [error, setError] = useState("");

  const scenario = scenarios.find((s) => s.id === scenarioId);
  const key = scenarioId ? `${iteration}:${scenarioId}` : "";
  const trace = key ? cache[key] ?? null : null;
  const ready = scenarioId ? iterationReady(iteration, scenarioId) : false;

  useEffect(() => {
    if (!scenarioId || cache[key] || !ready) {
      return;
    }
    let stale = false;
    api
      .trace(runId, iteration, scenarioId)
      .then((tr) => {
        if (!stale) {
          setCache((c) => ({ ...c, [key]: tr }));
          setError("");
        }
      })
      .catch((e) => !stale && setError(e.message));
    return () => {
      stale = true;
    };
  }, [runId, iteration, scenarioId, key, ready, cache]);

  useEffect(() => {
    setT(0);
    setPlaying(false);
  }, [scenarioId]);

  const end = trace?.sim_ms || scenario?.duration_ms || 1000;

  const tRef = useRef(t);
  tRef.current = t;
  useEffect(() => {
    if (!playing) {
      return;
    }
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const next = tRef.current + (now - last) * speed;
      last = now;
      if (next >= end) {
        setT(end);
        setPlaying(false);
        return;
      }
      setT(next);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, end]);

  const results: AssertionResult[] = useMemo(() => report?.matrix?.[String(iteration)]?.[scenarioId ?? ""] ?? [], [report, iteration, scenarioId]);
  const violations: Violation[] = useMemo(() => results.filter((r) => r.status === "fail").flatMap((r) => r.violations), [results]);
  const descriptions = useMemo(() => new Map(assertions.map((a) => [a.id, a.description])), [assertions]);

  if (!scenarios.length) {
    return null;
  }

  const visible = trace ? trace.serial_log.filter((l) => l.t_ms <= t) : [];

  return (
    <Panel
      title="Replay on the virtual board"
      right={
        <select aria-label="Scenario" className="field w-auto max-w-[320px] py-1 text-[12px]" value={scenarioId ?? ""} onChange={(e) => onScenario(e.target.value)}>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      }
    >
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <div className="border-b border-line p-3 lg:border-b-0 lg:border-r">
          <VirtualBoard pins={pins} trace={trace} t={t} scenario={scenario} tag={afterIteration === null ? undefined : side === "before" ? "BEFORE FIX" : "AFTER FIX"} />

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button aria-label={playing ? "Pause" : "Play"} className="btn-primary h-9 w-9 p-0" disabled={!trace} onClick={() => {
              if (t >= end) {
                setT(0);
              }
              setPlaying(!playing);
            }}>
              <Icon name={playing ? "pause" : "play"} />
            </button>
            <button aria-label="Restart" className="btn-ghost h-9 w-9 p-0" onClick={() => setT(0)}>
              <Icon name="restart" />
            </button>
            <input aria-label="Scrub replay time" type="range" className="scrub min-w-[140px] flex-1" min={0} max={end} step={1} value={Math.min(t, end)} onChange={(e) => setT(Number(e.target.value))} />
            <span className="font-mono text-[12px] text-muted">
              {fmtTime(t)} / {fmtTime(end)}
            </span>
            <div className="flex rounded-md border border-line bg-raised p-0.5" role="group" aria-label="Playback speed">
              {SPEEDS.map((s) => (
                <button key={s} aria-pressed={speed === s} onClick={() => setSpeed(s)} className={`rounded px-1.5 py-0.5 font-mono text-[11px] ${speed === s ? "bg-line text-ink" : "text-faint hover:text-ink"}`}>
                  {s}x
                </button>
              ))}
            </div>
          </div>

          {afterIteration !== null && (
            <div className="mt-3 flex rounded-md border border-line bg-raised p-1" role="group" aria-label="Firmware version">
              {(["before", "after"] as const).map((v) => (
                <button key={v} aria-pressed={side === v} onClick={() => setSide(v)} className={`flex-1 rounded py-1.5 text-[13px] font-medium transition-colors ${side === v ? (v === "before" ? "bg-fail/15 text-fail" : "bg-pass/15 text-pass") : "text-muted hover:text-ink"}`}>
                  {v === "before" ? "Before fix" : `After fix (patch ${afterIteration})`}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex min-w-0 flex-col">
          <div className="border-b border-line p-3">
            <h3 className="panel-title mb-1">Hypothesis</h3>
            <p className="text-[13px] text-muted">{scenario?.hypothesis || "No hypothesis recorded."}</p>
            {trace && (
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge tone={trace.exit_reason === "completed" ? "neutral" : "fail"}>exit: {trace.exit_reason}</Badge>
                <Badge>{(trace.cycles / 1e6).toFixed(0)}M cycles</Badge>
                {trace.pin_events_trimmed_from && <Badge tone="warn">replay shows first 8000 of {trace.pin_events_trimmed_from} events</Badge>}
              </div>
            )}
          </div>
          <div className="max-h-[230px] overflow-auto border-b border-line p-3">
            <h3 className="panel-title mb-1.5">Checks on this run</h3>
            {results.length === 0 && <p className="text-[12px] text-faint">Results appear when the run finishes.</p>}
            <ul className="space-y-1.5">
              {results.map((r) => (
                <li key={r.assertion_id} className="flex gap-1.5 text-[12px]">
                  <span className="mt-0.5 shrink-0">
                    {r.status === "pass" && <Icon name="check" className="text-pass" />}
                    {r.status === "fail" && <Icon name="x" className="text-fail" />}
                    {r.status === "not_exercised" && <Icon name="dash" className="text-faint" />}
                  </span>
                  <span className="min-w-0">
                    <span className="text-ink">{descriptions.get(r.assertion_id) ?? r.type}</span>
                    <span className={`block ${r.status === "not_exercised" ? "text-faint" : "text-muted"}`}>{r.evidence}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <SerialMonitor lines={visible} total={trace?.serial_log.length ?? 0} />
        </div>
      </div>

      <div className="border-t border-line p-3">
        {error && <p className="text-[13px] text-fail">Could not load the trace: {error}</p>}
        {trace ? (
          <TraceChart trace={trace} pins={pins} scenario={scenario} violations={violations} t={t} end={end} onScrub={setT} />
        ) : (
          <p className="py-8 text-center text-[13px] text-faint">{ready ? "Loading trace…" : "This scenario has not run yet."}</p>
        )}
      </div>
    </Panel>
  );
}

function SerialMonitor({ lines, total }: { lines: { t_ms: number; text: string }[]; total: number }) {
  const box = useRef<HTMLDivElement>(null);
  const shown = lines.slice(-150);
  useEffect(() => {
    if (box.current) {
      box.current.scrollTop = box.current.scrollHeight;
    }
  }, [lines.length]);
  return (
    <div className="flex flex-col p-3">
      <h3 className="panel-title mb-1.5">
        Serial monitor <span className="font-mono normal-case tracking-normal text-faint">{lines.length} of {total} lines</span>
      </h3>
      <div ref={box} className="h-[210px] overflow-auto rounded-md border border-line bg-bg p-2 font-mono text-[11.5px] leading-[1.45]" aria-live="off">
        {shown.length === 0 && <span className="text-faint">No output yet.</span>}
        {shown.map((l, i) => (
          <div key={`${l.t_ms}-${i}`} className="flex gap-2 whitespace-pre">
            <span className="shrink-0 text-faint">{(l.t_ms / 1000).toFixed(3)}</span>
            <span className="text-ink">{l.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
