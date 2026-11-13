import { useEffect, useRef, useState } from "react";
import { PinSpec, Scenario, Trace, Violation } from "../api";
import { fmtTime } from "../trace";
import { Icon } from "./Common";
import { TraceChart } from "./TraceChart";
import { Collapsible, Scrubber, Segmented, Select, Ticking } from "./ui";
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
  const resume = useRef(false);

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
        <Select label="Scenario" className="w-auto max-w-[min(360px,100%)] py-1.5" value={scenarioId ?? ""} onChange={onScenario} options={scenarios.map((s) => ({ value: s.id, label: s.name }))} />
        {hasAfter && (
          <Segmented
            label="Firmware version"
            value={side}
            onChange={onSide}
            options={[
              { value: "before", label: "Before" },
              { value: "after", label: "After" },
            ]}
          />
        )}
      </div>

      <div className="screen rounded-xl border border-[#0b0f0e] bg-screen text-screen-ink shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]">
        <div className="relative px-3 pt-3">
          <VirtualBoard pins={pins} trace={trace} t={t} scenario={scenario} />
          {!trace && <p className="absolute bottom-3 left-0 right-0 text-center text-xs text-screen-muted">{error ? `Could not load the trace: ${error}` : ready ? "Loading" : "Not run yet"}</p>}
        </div>

        <div className="flex items-center gap-3 px-4 pb-3 pt-1">
          <button
            aria-label={playing ? "Pause" : "Play"}
            className="key h-9 w-9 shrink-0 rounded-md bg-trace text-screen disabled:opacity-40"
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
          <Scrubber
            label="Replay time"
            value={Math.min(t, end)}
            max={end}
            valueText={`${fmtTime(t)} of ${fmtTime(end)}`}
            disabled={!trace}
            onChange={setT}
            onScrubStart={() => {
              resume.current = playing;
              setPlaying(false);
            }}
            onScrubEnd={() => {
              if (resume.current && tRef.current < end) {
                setPlaying(true);
              }
              resume.current = false;
            }}
          />
          <span className="num shrink-0 whitespace-nowrap text-right text-xs text-screen-muted" aria-hidden="true">
            <span className="text-screen-ink">{fmtTime(t)}</span> / {fmtTime(end)}
          </span>
          <button aria-label={`Playback speed ${speed} times. Change speed`} className="key num w-11 shrink-0 rounded py-1 text-xs !font-normal text-screen-muted hover:text-screen-ink" onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}>
            {speed}×
          </button>
        </div>

        <Collapsible.Root open={chart} onOpenChange={setChart} className="border-t border-screen-line">
          <Collapsible.Trigger className="flex w-full items-center gap-2 px-4 py-2.5 text-xs text-screen-muted transition-colors hover:text-screen-ink data-[state=open]:text-screen-ink">
            <Icon name="chevron" className="chev h-3 w-3" /> Signal trace
          </Collapsible.Trigger>
          <Collapsible.Content className="fold">
            {trace && (
              <div className="px-4 pb-4">
                <TraceChart trace={trace} pins={pins} scenario={scenario} violations={violations} t={t} end={end} onScrub={setT} />
              </div>
            )}
          </Collapsible.Content>
        </Collapsible.Root>
      </div>

      {evidence && (
        <p className="mt-4 text-base" aria-label="Measured evidence">
          <span className="text-muted">Before the fix, </span>
          <Ticking key={`b-${evidence.before}`} className="num text-sm text-fail" text={evidence.before} />
          {evidence.after && (
            <>
              <span className="text-muted">. After it, </span>
              <Ticking key={`a-${evidence.after}`} className="num text-sm text-pass" text={evidence.after} />
            </>
          )}
          <span className="text-muted">.</span>
        </p>
      )}
    </section>
  );
}
