import { useEffect, useRef, useState } from "react";
import { PinSpec, Scenario, Trace } from "../api";
import { keyFact } from "../format";
import { Icon } from "./Common";
import { Lamp, reducedMotion } from "./ui";
import { VirtualBoard } from "./VirtualBoard";

/** One finished run's stored traces, exported to public/demo so the landing works with an empty history. */
interface Demo {
  source: { run: string; title: string; scenario: string };
  pins: PinSpec[];
  scenario: Scenario;
  evidence: { before: string; after: string };
  before: Trace;
  after: Trace;
}

type Side = "before" | "after";

// Simulated milliseconds to play for each side. The fan starts chattering at 1.4 s.
const LOOP: { side: Side; from: number; to: number }[] = [
  { side: "before", from: 1000, to: 6000 },
  { side: "after", from: 1000, to: 5000 },
];
const HOLD = 900;
const FADE = 200;
// Under reduced motion: one frame mid-chatter, with the fan on.
const STILL = { side: "before" as Side, t: 5200 };
const FRAME_MS = 33;

/** Where the loop is after `elapsed` ms: which side, its simulated time, and whether the board is fading between sides. */
function at(elapsed: number): { side: Side; t: number; dim: boolean } {
  const total = LOOP.reduce((n, s) => n + (s.to - s.from) + HOLD, 0);
  let left = elapsed % total;
  for (const s of LOOP) {
    const span = s.to - s.from + HOLD;
    if (left < span) {
      return { side: s.side, t: Math.min(s.from + left, s.to), dim: left > span - FADE };
    }
    left -= span;
  }
  return { side: "before", t: LOOP[0].from, dim: false };
}

/** The landing's scope screen: the thermostat replay looping quietly, before the fix and after it. */
export function HeroScope() {
  const [demo, setDemo] = useState<Demo | null>(null);
  const [playing, setPlaying] = useState(() => !reducedMotion());
  const [visible, setVisible] = useState(true);
  const [frame, setFrame] = useState<{ side: Side; t: number; dim: boolean }>(() => (reducedMotion() ? { ...STILL, dim: false } : { side: "before", t: LOOP[0].from, dim: false }));
  const elapsed = useRef(0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/demo/thermostat-hover.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setDemo)
      .catch(() => setDemo(null));
  }, []);

  useEffect(() => {
    const el = box.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      return;
    }
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.1 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!demo || !playing || !visible) {
      return;
    }
    let raf = 0;
    let last = performance.now();
    let drawn = 0;
    const tick = (now: number) => {
      elapsed.current += now - last;
      last = now;
      // The board is a few hundred SVG nodes; thirty redraws a second is smooth for a fan and a gauge, and half the work.
      if (now - drawn >= FRAME_MS) {
        drawn = now;
        setFrame(at(elapsed.current));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [demo, playing, visible]);

  const trace = demo ? demo[frame.side] : null;
  const after = frame.side === "after";

  return (
    <figure className="m-0">
      <div ref={box} className="screen relative overflow-hidden rounded-xl border border-[#0b0f0e] bg-screen text-screen-ink shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]">
        <div aria-hidden="true">
          <p className="absolute left-4 top-3.5 z-10 flex items-center gap-2 text-xs text-screen-ink">
            <Lamp tone={after ? "pass" : "fail"} />
            <span className="transition-opacity duration-200" style={{ opacity: frame.dim ? 0.4 : 1 }}>
              {after ? "After the fix" : "Before the fix"}
            </span>
          </p>
          <div className="h-[280px] px-3 pb-2 pt-9 transition-opacity duration-200 ease-in-out sm:h-[360px] lg:h-[420px]" style={{ opacity: !demo ? 0 : frame.dim ? 0.35 : 1 }}>
            {demo && <VirtualBoard pins={demo.pins} trace={trace} t={frame.t} scenario={demo.scenario} className="block h-full w-full" />}
          </div>
        </div>
        <button
          aria-label={playing ? "Pause the replay" : "Play the replay"}
          className="key absolute right-3 top-2.5 z-10 grid h-7 w-7 place-items-center rounded-md text-screen-muted hover:text-screen-ink"
          disabled={!demo}
          onClick={() => setPlaying(!playing)}
        >
          <Icon name={playing ? "pause" : "play"} className="h-3.5 w-3.5" />
        </button>
      </div>
      <figcaption className="mt-3 min-h-[60px] text-sm text-muted sm:min-h-10">
        {demo ? `Replay of a finished run. Before the fix, ${keyFact(demo.evidence.before)}. After it, ${keyFact(demo.evidence.after)}.` : "Replay of a finished run."}
      </figcaption>
    </figure>
  );
}
