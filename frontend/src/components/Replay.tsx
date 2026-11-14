import { useEffect, useRef, useState } from "react";
import { Bug, ChevronDown, CircleCheck } from "lucide-react";
import { PinSpec, Scenario, Trace, Violation } from "../api";
import { iconProps } from "../icons";
import { fmtTime } from "../trace";
import { BoardStage, StageChip } from "./BoardStage";
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
  /** Where the board opens, paused, for each scenario. Null until it is known. */
  startAt: number | null;
  /** Rule lamps on the board, lit by how each check came out in this scenario. */
  chips?: StageChip[];
  onChip?: (chip: StageChip) => void;
  activeChip?: string | null;
}

const SPEEDS = [0.25, 0.5, 1, 2, 4];

/** The board replay: one scenario, one firmware version at a time, and the single number that shows the difference. */
export function Replay({ pins, scenarios, scenarioId, onScenario, trace, error, ready, side, onSide, hasAfter, violations, evidence, startAt, chips, onChip, activeChip }: Props) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [chart, setChart] = useState(false);
  const resume = useRef(false);

  const scenario = scenarios.find((s) => s.id === scenarioId);
  const end = trace?.sim_ms || scenario?.duration_ms || 1000;

  const placed = useRef<string | null>(null);
  useEffect(() => {
    if (placed.current === scenarioId) {
      return;
    }
    setT(startAt ?? 0);
    setPlaying(false);
    if (startAt !== null) {
      placed.current = scenarioId;
    }
  }, [scenarioId, startAt]);

  const tRef = useRef(t);
  tRef.current = t;
  const switchSide = (next: "before" | "after") => {
    if (startAt !== null && (tRef.current <= 0 || tRef.current >= end)) {
      setT(startAt);
      setPlaying(false);
    }
    onSide(next);
  };
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
        <Select
          label="Scenario"
          className="w-auto max-w-[min(360px,100%)] !border-line !bg-white"
          value={scenarioId ?? ""}
          onChange={onScenario}
          options={scenarios.map((s) => ({ value: s.id, label: s.name }))}
        />
        {hasAfter && (
          <Segmented
            label="Firmware version"
            value={side}
            onChange={switchSide}
            options={[
              {
                value: "before",
                label: (
                  <>
                    <Bug {...iconProps} />
                    Before
                  </>
                ),
              },
              {
                value: "after",
                label: (
                  <>
                    <CircleCheck {...iconProps} />
                    After
                  </>
                ),
              },
            ]}
          />
        )}
      </div>

      <div className="screen overflow-hidden rounded-xl border border-[#0b0f0e] bg-screen text-screen-ink shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]">
        <div className="relative w-full pt-1 sm:px-3 sm:pt-3">
          <div className="w-full sm:mx-auto sm:max-w-[960px]">
            {chips?.length ? <BoardStage pins={pins} trace={trace} t={t} scenario={scenario} chips={chips} onChip={onChip} activeChip={activeChip} /> : <VirtualBoard pins={pins} trace={trace} t={t} scenario={scenario} className="block w-full" />}
          </div>
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
          <Collapsible.Trigger className="flex w-full items-center gap-2 px-4 py-2.5 text-xs text-screen-muted transition-colors hover:text-screen-ink data-[state=open]:text-screen-ink" aria-label={chart ? "Collapse signal trace" : "Expand signal trace"}>
            <ChevronDown {...iconProps} className={`transition-transform ${chart ? "rotate-180" : ""}`} aria-hidden="true" /> Signal trace
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
