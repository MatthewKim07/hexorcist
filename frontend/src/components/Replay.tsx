import { useEffect, useRef, useState } from "react";
import { PinSpec, Scenario, Trace, Violation } from "../api";
import { fmtTime } from "../trace";
import { Icon } from "./Common";
import { TraceChart } from "./TraceChart";
import { VirtualBoard } from "./VirtualBoard";

interface Props {
  pins: PinSpec[];
  scenarios: Scenario[];
  scenarioId: string | null;
  onScenario: (id: string) => void;
  trace: Trace | null;
  error: string;
  /** Whether this scenario has finished running for the chosen firmware version. */
  ready: boolean;
  side: "before" | "after";
  onSide: (side: "before" | "after") => void;
  /** Null when there is no patch to compare against. */
  hasAfter: boolean;
  violations: Violation[];
  evidence: { before: string; after: string } | null;
}

const SPEEDS = [0.25, 0.5, 1, 2, 4];

/** The board replay: one scenario, one firmware version at a time, and the single number that shows the difference. */
export function Replay({ pins, scenarios, scenarioId, onScenario, trace, error, ready, side, onSide, hasAfter, violations, evidence }: Props) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [chart, setChart] = useState(false);

  const scenario = scenarios.find((s) => s.id === scenarioId);
  const end = trace?.sim_ms || scenario?.duration_ms || 1000;

  useEffect(() => {
    setT(0);
    setPlaying(false);
  }, [scenarioId]);

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

  if (!scenarios.length) {
    return null;
  }

  return (
    <section id="replay" className="scroll-mt-20">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <select aria-label="Scenario" className="field w-auto max-w-[min(360px,100%)] py-1.5" value={scenarioId ?? ""} onChange={(e) => onScenario(e.target.value)}>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        {hasAfter && (
          <div className="flex rounded-md border border-line p-0.5" role="group" aria-label="Firmware version">
            {(["before", "after"] as const).map((v) => (
              <button key={v} aria-pressed={side === v} onClick={() => onSide(v)} className={`rounded px-5 py-1.5 text-[14px] transition-colors ${side === v ? (v === "before" ? "bg-fail/15 text-fail" : "bg-pass/15 text-pass") : "text-muted hover:text-ink"}`}>
                {v === "before" ? "Before" : "After"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="relative overflow-hidden rounded-lg bg-raised p-3">
        <VirtualBoard pins={pins} trace={trace} t={t} scenario={scenario} />
        {!trace && <p className="absolute bottom-3 left-0 right-0 text-center text-[13px] text-faint">{error ? `Could not load the trace: ${error}` : ready ? "Loading…" : "Not run yet"}</p>}
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button
          aria-label={playing ? "Pause" : "Play"}
          className="btn-primary h-9 w-9 shrink-0 !p-0"
          disabled={!trace}
          onClick={() => {
            if (t >= end) {
              setT(0);
            }
            setPlaying(!playing);
          }}
        >
          <Icon name={playing ? "pause" : "play"} />
        </button>
        <input aria-label="Scrub replay time" type="range" className="scrub min-w-0 flex-1" min={0} max={end} step={1} value={Math.min(t, end)} onChange={(e) => setT(Number(e.target.value))} />
        <span className="num shrink-0 whitespace-nowrap text-right text-muted">
          {fmtTime(t)} / {fmtTime(end)}
        </span>
        <button
          aria-label={`Playback speed ${speed}x, click to change`}
          className="num w-10 shrink-0 rounded text-faint hover:text-ink"
          onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}
        >
          {speed}x
        </button>
      </div>

      {evidence && (
        <p className="mt-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[16px]" aria-label="Measured evidence">
          <span className="whitespace-nowrap">
            <span className="text-faint">Before </span>
            <span className="num !text-[15px] text-fail">{evidence.before}</span>
          </span>
          {evidence.after && (
            <>
              <span className="text-faint">→</span>
              <span className="whitespace-nowrap">
                <span className="text-faint">After </span>
                <span className="num !text-[15px] text-pass">{evidence.after}</span>
              </span>
            </>
          )}
        </p>
      )}

      <div className="mt-4">
        <button className="flex items-center gap-1.5 text-[13px] text-muted hover:text-ink" aria-expanded={chart} onClick={() => setChart(!chart)}>
          <Icon name="chevron" className={`h-3 w-3 transition-transform ${chart ? "rotate-90" : ""}`} /> Signal trace
        </button>
        {chart && trace && (
          <div className="mt-3">
            <TraceChart trace={trace} pins={pins} scenario={scenario} violations={violations} t={t} end={end} onScrub={setT} />
          </div>
        )}
      </div>
    </section>
  );
}
