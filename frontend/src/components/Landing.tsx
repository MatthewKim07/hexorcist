import { useEffect, useState } from "react";
import { api, Health, Preset } from "../api";
import { useStripText } from "./Chassis";

/** A run of an example, with the checks the example ships, so the run measures exactly what its chips say. */
export function startPreset(p: Preset, compare = false) {
  return api.start({ mode: "break", title: p.title, firmware: p.firmware, pins: p.pins, behaviour: p.behaviour, compare, ...(p.checks ? { checks: p.checks } : {}) });
}

/** Short card copy for each preset. Tags stay short and mono. */
const CARD: Record<string, { blurb: string; tag: string }> = {
  thermostat: { blurb: "Fan chatters near the threshold", tag: "hysteresis" },
  button: { blurb: "One press toggles the LED many times", tag: "debounce" },
  logger: { blurb: "Printed temperature is scaled wrong", tag: "units" },
  alarm: { blurb: "Short presses never reach the siren", tag: "blocking delay" },
  containment: { blurb: "Uploads hostile code. Nothing should escape.", tag: "security demo" },
};

export function Landing({ health, onStarted }: { health: Health | null; onStarted: (id: string) => void }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  useStripText(busyId ? "Starting" : "");

  useEffect(() => {
    api
      .presets()
      .then(setPresets)
      .catch((e) => setError(e.message));
  }, []);

  const run = async (p: Preset) => {
    setBusyId(p.id);
    setError("");
    try {
      onStarted((await startPreset(p)).run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusyId(null);
    }
  };

  const canRun = health === null || health.llm_configured;
  const bugs = presets.filter((p) => p.id !== "containment");
  const containment = presets.find((p) => p.id === "containment");

  return (
    <div>
      <h1 className="text-[32px] font-semibold leading-tight tracking-[-0.03em] text-ink">Break your firmware.</h1>
      <p className="mt-3 text-sm text-muted">Hexorcist attacks your Arduino sketch on an emulated chip, then proves the fix.</p>

      <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {bugs.map((p) => {
          const card = CARD[p.id] ?? { blurb: p.summary, tag: p.id };
          const busy = busyId === p.id;
          const disabled = !!busyId || !canRun;
          return (
            <article key={p.id} className="preset-card flex h-full flex-col border border-line bg-white p-5 transition-[border-color] duration-150">
              <h2 className="text-sm font-medium text-ink">{p.title}</h2>
              <p className="mt-1.5 text-sm text-muted">{card.blurb}</p>
              <div className="mt-auto flex items-center justify-between gap-3 pt-4">
                <span className="font-mono text-xs text-muted">{card.tag}</span>
                <button type="button" className="key shrink-0 border border-line bg-white px-3 py-1.5 text-sm !font-normal text-ink disabled:opacity-50" style={{ borderRadius: 8 }} disabled={disabled} onClick={() => run(p)}>
                  {busy ? "Starting…" : "Run"}
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {containment && (
        <div className="mt-8">
          <p className="mb-3 text-xs text-muted">Security</p>
          <article className="preset-card flex flex-col gap-3 border border-line bg-white p-5 transition-[border-color] duration-150 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-sm font-medium text-ink">{containment.title}</h2>
                <span className="font-mono text-xs text-muted">{CARD.containment.tag}</span>
              </div>
              <p className="mt-1.5 text-sm text-muted">{CARD.containment.blurb}</p>
            </div>
            <button
              type="button"
              className="key shrink-0 self-end border border-line bg-white px-3 py-1.5 text-sm !font-normal text-ink disabled:opacity-50 sm:self-center"
              style={{ borderRadius: 8 }}
              disabled={!!busyId}
              onClick={() => run(containment)}
            >
              {busyId === containment.id ? "Starting…" : "Run"}
            </button>
          </article>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-fail">{error}</p>}

      <p className="mt-10">
        <a href="#/new" className="text-sm text-muted transition-colors hover:text-ink">
          Use your own sketch →
        </a>
      </p>
    </div>
  );
}
