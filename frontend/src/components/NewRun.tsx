import { useEffect, useRef, useState } from "react";
import { api, Health, PinSpec, Preset } from "../api";
import { usePasscodeGate } from "./Chassis";
import { PinTable } from "./PinTable";
import { Checkbox, Segmented } from "./ui";

type Mode = "break" | "build";

const BUILD_EXAMPLES = [
  { label: "Greenhouse fan", text: "A greenhouse fan: LM35 temperature sensor on A0 (10 mV/°C), fan on D9. Fan on at 28 °C, off at 25 °C. If the sensor fails, run the fan." },
  { label: "Door chime", text: "A door chime: push button on D2 to ground, buzzer on D8. Each press sounds the buzzer for exactly 1 second, and a heartbeat line prints every second." },
  { label: "Light logger", text: "A light logger: photoresistor on A0, 1 mV per mV. Print the reading every 500 ms, and turn the LED on D13 on when it stays below 1000 mV." },
];

export function NewRun({ health, onStarted, initialMode = "break" }: { health: Health | null; onStarted: (id: string) => void; initialMode?: Mode }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [firmware, setFirmware] = useState("");
  const [pins, setPins] = useState<PinSpec[]>([]);
  const [behaviour, setBehaviour] = useState("");
  const [compare, setCompare] = useState(false);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const withPasscode = usePasscodeGate();

  useEffect(() => {
    api.presets().then(setPresets).catch(() => undefined);
  }, []);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  const llm = health === null || health.llm_configured;
  const breakReady = !!firmware.trim() && !!behaviour.trim() && pins.length > 0;
  const buildReady = !!description.trim();
  const ready = mode === "break" ? breakReady : buildReady;
  const why = busy || ready || !llm ? (!llm && !busy ? "No model configured" : "") : mode === "break" ? (!firmware.trim() ? "Paste a sketch" : pins.length === 0 ? "Add at least one pin" : !behaviour.trim() ? "Say what it must do" : "") : !description.trim() ? "Describe a device" : "";

  const fillExample = () => {
    const t = presets.find((p) => p.id === "thermostat");
    if (!t) {
      return;
    }
    setMode("break");
    setFirmware(t.firmware);
    setPins(t.pins);
    setBehaviour(t.behaviour);
    setError("");
  };

  const onUpload = async (file: File | null) => {
    if (!file) {
      return;
    }
    setFirmware(await file.text());
  };

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await withPasscode(async () => {
        if (mode === "build") {
          onStarted((await api.start({ mode: "build", title: description.slice(0, 60), description, pins: [] })).run_id);
          return;
        }
        const thermo = presets.find((p) => p.id === "thermostat");
        const same = thermo && firmware === thermo.firmware && behaviour === thermo.behaviour;
        const { run_id } = await api.start({
          mode: "break",
          title: same ? thermo!.title : "",
          firmware,
          pins,
          behaviour,
          compare,
          ...(same && thermo?.checks ? { checks: thermo.checks } : {}),
        });
        onStarted(run_id);
      });
    } catch (e) {
      const msg = (e as Error).message;
      if (msg !== "Passcode cancelled") {
        setError(msg);
      }
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[720px]">
      <a href="#/" className="text-sm text-muted transition-colors hover:text-ink">
        ← Back
      </a>
      <h1 className="mt-6 text-[32px] font-semibold leading-tight tracking-[-0.03em] text-ink">New run</h1>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Mode"
          value={mode}
          onChange={setMode}
          options={[
            { value: "break", label: "Find bugs" },
            { value: "build", label: "Write firmware" },
          ]}
        />
        {mode === "break" && (
          <button type="button" className="text-sm text-muted transition-colors hover:text-ink" onClick={fillExample} disabled={!presets.some((p) => p.id === "thermostat")}>
            Fill with an example
          </button>
        )}
      </div>

      <div className="mt-8 space-y-6">
        {mode === "break" ? (
          <>
            <div>
              <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                <label htmlFor="sketch" className="form-label">
                  Sketch
                </label>
                <button type="button" className="key border border-line bg-white px-2.5 py-1 text-xs !font-normal text-ink" style={{ borderRadius: 6 }} onClick={() => fileRef.current?.click()}>
                  Upload .ino
                </button>
                <input ref={fileRef} type="file" accept=".ino,.cpp,.c,.h,text/plain" className="hidden" onChange={(e) => onUpload(e.target.files?.[0] ?? null)} />
              </div>
              <p className="mb-2 text-sm text-muted">Arduino Uno sketch. Compiles and runs only in the sandbox.</p>
              <textarea id="sketch" rows={16} className="form-input scroll font-mono text-[13px] leading-relaxed" value={firmware} onChange={(e) => setFirmware(e.target.value)} placeholder={"void setup()\n{\n  pinMode(9, OUTPUT);\n}\n\nvoid loop()\n{\n}"} spellCheck={false} />
            </div>

            <div>
              <div className="form-label mb-1.5">Pins</div>
              <p className="mb-2 text-sm text-muted">What is wired to the board: inputs the tests drive, outputs the checks watch.</p>
              <PinTable pins={pins} onChange={setPins} />
            </div>

            <div>
              <label htmlFor="behaviour" className="form-label mb-1.5 block">
                Behaviour
              </label>
              <p className="mb-2 text-sm text-muted">What it must do, with numbers.</p>
              <textarea id="behaviour" rows={5} className="form-input scroll leading-relaxed" value={behaviour} onChange={(e) => setBehaviour(e.target.value)} placeholder="Fan on at 30 °C, off at 27 °C…" />
            </div>

            <Checkbox checked={compare} onChange={setCompare} className="text-sm text-muted" hint="Extra guess with no emulator, shown next to the measured results">
              Compare with a plain AI code review
            </Checkbox>
          </>
        ) : (
          <div>
            <label htmlFor="description" className="form-label mb-1.5 block">
              Device
            </label>
            <p className="mb-2 text-sm text-muted">Sensors, outputs, pins, behaviour. It writes the firmware, then attacks it.</p>
            <textarea id="description" rows={8} className="form-input scroll leading-relaxed" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="A greenhouse fan: LM35 on A0…" />
            <div className="mt-3 flex flex-wrap gap-2">
              {BUILD_EXAMPLES.map((e) => (
                <button key={e.label} type="button" className="key border border-line bg-white px-2.5 py-1 text-xs !font-normal text-muted hover:text-ink" style={{ borderRadius: 6 }} onClick={() => setDescription(e.text)}>
                  {e.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="mt-10">
        {error && <p className="mb-3 text-sm text-fail">{error}</p>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end sm:gap-3">
          {why && <p className="text-[13px] text-muted">{why}</p>}
          <button type="button" className="btn-primary w-full sm:w-auto" disabled={!ready || busy || !llm} onClick={start}>
            {busy ? "Starting…" : "Start run"}
          </button>
        </div>
      </div>
    </div>
  );
}
