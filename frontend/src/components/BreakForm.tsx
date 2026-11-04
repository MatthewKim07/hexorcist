import { useEffect, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import { tokyoNightInit } from "@uiw/codemirror-theme-tokyo-night";
import { tags } from "@lezer/highlight";
import { api, PinSpec, Preset } from "../api";
import { Icon, Panel } from "./Common";
import { PinTable } from "./PinTable";

// The stock theme's comments are too dim to read on a screen recording.
const editorTheme = tokyoNightInit({ styles: [{ tag: [tags.comment, tags.lineComment, tags.blockComment], color: "#8b93a7" }] });

const STARTER = `void setup()
{
    pinMode(LED_BUILTIN, OUTPUT);
}

void loop()
{
    digitalWrite(LED_BUILTIN, HIGH);
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
    delay(500);
}
`;

export function BreakForm({ onStarted }: { onStarted: (id: string) => void }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [firmware, setFirmware] = useState(STARTER);
  const [pins, setPins] = useState<PinSpec[]>([{ pin: "D13", role: "Status LED", type: "digital_output", scale: "", active_low: false }]);
  const [behaviour, setBehaviour] = useState("The LED blinks with 500 ms on and 500 ms off.");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.presets().then(setPresets).catch((e) => setError(`Could not load presets: ${e.message}`));
  }, []);

  const load = (p: Preset) => {
    setActive(p.id);
    setTitle(p.title);
    setFirmware(p.firmware);
    setPins(p.pins);
    setBehaviour(p.behaviour);
    setError("");
  };

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const { run_id } = await api.start({ mode: "break", title, firmware, pins, behaviour });
      onStarted(run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Is your firmware possessed?</h1>
        <p className="mt-1 max-w-2xl text-muted">Hand over a sketch and what it should do. The agent attacks the real compiled binary on an emulated ATmega328P, in a sealed sandbox, then proves its fix by running everything again.</p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {presets.map((p) => {
          const hostile = p.id === "containment";
          return (
            <button
              key={p.id}
              onClick={() => load(p)}
              className={`rounded-lg border p-3 text-left transition-colors ${active === p.id ? "border-halo/70 bg-halo/5" : "border-line bg-panel hover:border-faint"}`}
            >
              <div className="flex items-center gap-1.5 text-[13px] font-medium">
                {hostile && <Icon name="shield" className="text-halo" />}
                {p.title}
              </div>
              <div className="mt-1 text-[12px] leading-snug text-muted">{p.summary}</div>
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Panel title="Sketch (.ino)" className="overflow-hidden">
          <div className="h-[470px] overflow-hidden">
            <CodeMirror value={firmware} onChange={setFirmware} theme={editorTheme} extensions={[cpp()]} height="470px" aria-label="Arduino sketch" />
          </div>
        </Panel>

        <div className="space-y-4">
          <Panel title="Pin map, Arduino Uno">
            <div className="p-3">
              <PinTable pins={pins} onChange={setPins} />
            </div>
          </Panel>
          <Panel title="Intended behaviour">
            <div className="p-3">
              <textarea aria-label="Intended behaviour" rows={7} className="field resize-y leading-relaxed" value={behaviour} onChange={(e) => setBehaviour(e.target.value)} placeholder="Describe what the firmware must do, with numbers." />
            </div>
          </Panel>
          {error && <div className="rounded-md border border-fail/40 bg-fail/10 px-3 py-2 text-[13px] text-fail">{error}</div>}
          <button className="btn-primary w-full py-2.5" disabled={busy} onClick={start}>
            {busy ? "Starting…" : "Cast the bugs out"}
          </button>
        </div>
      </div>
    </div>
  );
}
