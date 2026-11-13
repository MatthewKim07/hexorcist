import { useEffect, useState } from "react";
import { api, Health, Preset, RunSummary } from "../api";
import { useStripText } from "./Chassis";
import { HeroScope } from "./HeroScope";

/** A run of an example, with the checks the example ships, so the run measures exactly what its chips say. */
export function startPreset(p: Preset, compare = false) {
  return api.start({ mode: "break", title: p.title, firmware: p.firmware, pins: p.pins, behaviour: p.behaviour, compare, ...(p.checks ? { checks: p.checks } : {}) });
}

export function Landing({ health, onStarted }: { health: Health | null; onStarted: (id: string) => void }) {
  const [thermostat, setThermostat] = useState<Preset | null>(null);
  const [finished, setFinished] = useState<RunSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useStripText(busy ? "Starting" : "Idle");

  useEffect(() => {
    api
      .presets()
      .then((list) => setThermostat(list.find((p) => p.id === "thermostat") ?? null))
      .catch((e) => setError(`Could not load the examples: ${e.message}`));
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

  return (
    <div className="space-y-6">
      <HeroScope />
      <div className="grid items-start gap-x-10 gap-y-5 md:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <h1 className="max-w-[30ch] text-lg font-semibold leading-snug tracking-tight">Breaks your Arduino firmware on an emulated chip, then proves the fix.</h1>
          <p className="mt-2 max-w-[60ch] text-sm text-muted">Paste a sketch, wire its pins, and say what it must do. Every check is measured on the real compiled firmware in a sealed sandbox, not read from the code.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn-primary" disabled={busy || !thermostat || (health !== null && !health.llm_configured)} onClick={run}>
            {busy ? "Starting" : "Run the thermostat"}
          </button>
          <a className="btn-outline" href="#/break">
            Set up your own
          </a>
          {finished && (
            <a href={`#/runs/${finished.id}`} className="link w-full text-sm md:text-right">
              Open a finished run
            </a>
          )}
        </div>
      </div>
      {error && <p className="text-fail">{error}</p>}
    </div>
  );
}
