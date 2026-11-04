import { useState } from "react";
import { api } from "../api";
import { Panel } from "./Common";

const EXAMPLES = [
  "A greenhouse fan: LM35 temperature sensor on A0 (10 mV/°C), fan on D9. Fan on at 28 °C, off at 25 °C. If the sensor fails, run the fan.",
  "A door chime: push button on D2 to ground, buzzer on D8. Each press sounds the buzzer for exactly 1 second, and a heartbeat line prints every second.",
  "A light logger: photoresistor on A0, 1 mV per mV. Print the reading every 500 ms, and turn the LED on D13 on when it stays below 1000 mV.",
];

export function BuildForm({ onStarted }: { onStarted: (id: string) => void }) {
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const { run_id } = await api.start({ mode: "build", title: description.slice(0, 60), description, pins: [] });
      onStarted(run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Describe it. Then watch it get attacked.</h1>
        <p className="mt-1 text-muted">The agent writes the firmware, fixes it from real compiler errors, then runs the full attack suite on its own code. It does not get to call its work done until the emulator agrees.</p>
      </div>
      <Panel title="What should the device do?">
        <div className="p-3">
          <textarea aria-label="Device description" rows={8} className="field resize-y leading-relaxed" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Name the sensors and outputs, the pins if you care, and the behaviour you want." />
          <div className="mt-3 space-y-1.5">
            <div className="text-[12px] text-faint">Or start from one of these</div>
            {EXAMPLES.map((text) => (
              <button key={text} onClick={() => setDescription(text)} className="block w-full rounded-md border border-line bg-raised px-3 py-2 text-left text-[13px] text-muted transition-colors hover:border-faint hover:text-ink">
                {text}
              </button>
            ))}
          </div>
        </div>
      </Panel>
      {error && <div className="rounded-md border border-fail/40 bg-fail/10 px-3 py-2 text-[13px] text-fail">{error}</div>}
      <button className="btn-primary w-full py-2.5" disabled={busy || !description.trim()} onClick={start}>
        {busy ? "Starting…" : "Build it, then try to break it"}
      </button>
    </div>
  );
}
