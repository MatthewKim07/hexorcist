import { useState } from "react";
import { api } from "../api";

const EXAMPLES = [
  { label: "Greenhouse fan", text: "A greenhouse fan: LM35 temperature sensor on A0 (10 mV/°C), fan on D9. Fan on at 28 °C, off at 25 °C. If the sensor fails, run the fan." },
  { label: "Door chime", text: "A door chime: push button on D2 to ground, buzzer on D8. Each press sounds the buzzer for exactly 1 second, and a heartbeat line prints every second." },
  { label: "Light logger", text: "A light logger: photoresistor on A0, 1 mV per mV. Print the reading every 500 ms, and turn the LED on D13 on when it stays below 1000 mV." },
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
    <div className="mx-auto max-w-2xl">
      <h1 className="headline">Describe a device</h1>
      <p className="mt-2 text-muted">It writes the firmware, then attacks it.</p>
      <textarea aria-label="Device description" rows={7} className="field scroll mt-8 resize-none leading-relaxed" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Sensors, outputs, pins, behaviour" />
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1">
        {EXAMPLES.map((e) => (
          <button key={e.label} onClick={() => setDescription(e.text)} className="key text-xs !font-normal text-muted hover:text-ink">
            {e.label}
          </button>
        ))}
      </div>
      {error && <p className="mt-4 text-fail">{error}</p>}
      <button className="btn-primary mt-8" disabled={busy || !description.trim()} onClick={start}>
        {busy ? "Starting" : "Build and attack"}
      </button>
    </div>
  );
}
