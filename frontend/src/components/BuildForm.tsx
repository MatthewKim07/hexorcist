import { useState } from "react";
import { api } from "../api";
import { useStripText } from "./Chassis";

const EXAMPLES = [
  { label: "Greenhouse fan", text: "A greenhouse fan: LM35 temperature sensor on A0 (10 mV/°C), fan on D9. Fan on at 28 °C, off at 25 °C. If the sensor fails, run the fan." },
  { label: "Door chime", text: "A door chime: push button on D2 to ground, buzzer on D8. Each press sounds the buzzer for exactly 1 second, and a heartbeat line prints every second." },
  { label: "Light logger", text: "A light logger: photoresistor on A0, 1 mV per mV. Print the reading every 500 ms, and turn the LED on D13 on when it stays below 1000 mV." },
];

export function BuildForm({ onStarted }: { onStarted: (id: string) => void }) {
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useStripText(busy ? "Starting" : description.trim() ? "Ready to build" : "Describe a device to start");

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
    <div className="space-y-5">
      <section aria-labelledby="build-title" className="screen rounded-xl border border-[#0b0f0e] bg-screen p-5 sm:p-6">
        <h1 id="build-title" className="text-lg font-semibold tracking-tight text-screen-ink">
          Describe a device
        </h1>
        <p className="mt-1 text-sm text-screen-muted">It writes the firmware from your description, then attacks it in the same sandbox.</p>
        <textarea
          aria-label="Device description"
          rows={7}
          className="scroll mt-5 w-full resize-y rounded-md border border-screen-line bg-screen-raised px-3.5 py-3 leading-relaxed text-screen-ink outline-none transition-colors placeholder:text-screen-muted focus:border-trace"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Sensors, outputs, pins, behaviour, with numbers"
        />
      </section>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-3">
        <span className="label mr-1">Start from</span>
        {EXAMPLES.map((e) => (
          <button key={e.label} aria-pressed={description === e.text} onClick={() => setDescription(e.text)} className="key rounded-full border border-line bg-raised px-3 py-1 text-xs !font-normal text-muted hover:text-ink aria-pressed:border-ink aria-pressed:text-ink">
            {e.label}
          </button>
        ))}
        <button className="btn-primary ml-auto" disabled={busy || !description.trim()} onClick={start}>
          {busy ? "Starting" : "Build and attack"}
        </button>
      </div>
      {error && <p className="text-fail">{error}</p>}
    </div>
  );
}
