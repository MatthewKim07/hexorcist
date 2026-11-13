import { useEffect, useRef, useState } from "react";
import { api, Health, Preset, RunSummary } from "../api";
import { useStripText } from "./Chassis";
import { HeroScope } from "./HeroScope";
import { reducedMotion } from "./ui";

/** A run of an example, with the checks the example ships, so the run measures exactly what its chips say. */
export function startPreset(p: Preset, compare = false) {
  return api.start({ mode: "break", title: p.title, firmware: p.firmware, pins: p.pins, behaviour: p.behaviour, compare, ...(p.checks ? { checks: p.checks } : {}) });
}

/** Reveal a pane once it is mostly on screen. One motion per section; none under reduced motion. */
function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [on, setOn] = useState(() => reducedMotion());
  useEffect(() => {
    const el = ref.current;
    if (!el || reducedMotion()) {
      setOn(true);
      return;
    }
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setOn(true), { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return { ref, on };
}

function Pane({ children, className = "", id }: { children: React.ReactNode; className?: string; id?: string }) {
  const { ref, on } = useReveal<HTMLElement>();
  return (
    <section ref={ref} id={id} data-in={on || undefined} className={`story-pane ${className}`}>
      {children}
    </section>
  );
}

export function Landing({ health, onStarted }: { health: Health | null; onStarted: (id: string) => void }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [thermostat, setThermostat] = useState<Preset | null>(null);
  const [finished, setFinished] = useState<RunSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useStripText(busy ? "Starting" : "");

  useEffect(() => {
    api
      .presets()
      .then((list) => setThermostat(list.find((p) => p.id === "thermostat") ?? null))
      .catch((e) => setError(e.message));
    api
      .runs()
      .then((runs) => {
        const done = runs.filter((r) => r.mode === "break" && r.status === "fixed");
        setFinished(done.find((r) => /thermostat/i.test(r.title)) ?? done[0] ?? null);
      })
      .catch(() => undefined);
  }, []);

  const run = async () => {
    if (!thermostat) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      onStarted((await startPreset(thermostat)).run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const toExample = () => {
    document.getElementById("example")?.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
  };

  return (
    <div ref={scroller} className="story -mx-4 -mb-8 -mt-3 sm:-mx-6">
      <Pane className="relative items-center justify-center text-center">
        <h1 className="text-[clamp(2.75rem,8vw,5.5rem)] font-semibold leading-none tracking-[-0.04em] text-ink">Hexorcist</h1>
        <p className="mt-5 max-w-[22ch] text-base text-muted sm:text-lg">Casts the bugs out of your firmware.</p>
        <button type="button" onClick={toExample} className="key absolute bottom-6 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2 !font-normal text-muted" aria-label="See an example">
          <span className="story-hint h-7 w-px bg-line" />
          <span className="text-xs">See an example</span>
        </button>
      </Pane>

      <Pane id="example" className="justify-center gap-5 px-4 sm:px-6">
        <p className="text-center text-sm text-muted">A fan that would not stay on.</p>
        <HeroScope quiet />
      </Pane>

      <Pane className="items-stretch justify-center gap-6 px-4 pb-10 sm:px-6">
        <p className="text-center text-sm text-muted">Your turn.</p>
        <div className="mx-auto grid w-full max-w-3xl gap-3 sm:grid-cols-3">
          <button
            type="button"
            disabled={busy || !thermostat || (health !== null && !health.llm_configured)}
            onClick={run}
            className="key flex min-h-[120px] flex-col items-start justify-between rounded-xl bg-ink p-5 text-left text-bg disabled:opacity-50"
          >
            <span className="text-xs text-bg/55">Example</span>
            <span className="text-lg font-semibold tracking-tight">{busy ? "Starting…" : "Try the fan"}</span>
          </button>
          <a href="#/break" className="key flex min-h-[120px] flex-col items-start justify-between rounded-xl border border-line bg-raised p-5 text-left text-ink">
            <span className="text-xs text-muted">Blank</span>
            <span className="text-lg font-semibold tracking-tight">Your sketch</span>
          </a>
          {finished ? (
            <a href={`#/runs/${finished.id}`} className="key flex min-h-[120px] flex-col items-start justify-between rounded-xl border border-line bg-raised p-5 text-left text-ink">
              <span className="text-xs text-muted">Done</span>
              <span className="text-lg font-semibold tracking-tight">A finished run</span>
            </a>
          ) : (
            <span className="flex min-h-[120px] flex-col items-start justify-between rounded-xl border border-dashed border-line p-5 text-left text-muted">
              <span className="text-xs">Done</span>
              <span className="text-lg font-semibold tracking-tight text-muted/70">No runs yet</span>
            </span>
          )}
        </div>
        {error && <p className="text-center text-sm text-fail">{error}</p>}
      </Pane>
    </div>
  );
}
