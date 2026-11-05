import { useEffect, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import { tokyoNightInit } from "@uiw/codemirror-theme-tokyo-night";
import { tags } from "@lezer/highlight";
import { api, PinSpec, Preset, RunSummary } from "../api";
import { Icon, Panel } from "./Common";
import { PinTable } from "./PinTable";

// The stock theme's comments are too dim to read on a screen recording.
const editorTheme = tokyoNightInit({ styles: [{ tag: [tags.comment, tags.lineComment, tags.blockComment], color: "#8b93a7" }] });

export function BreakForm({ onStarted }: { onStarted: (id: string) => void }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const thermostat = presets.find((p) => p.id === "thermostat");
  const [active, setActive] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [firmware, setFirmware] = useState("");
  const [pins, setPins] = useState<PinSpec[]>([]);
  const [behaviour, setBehaviour] = useState("");
  const [finished, setFinished] = useState<RunSummary | null>(null);
  const [compare, setCompare] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .presets()
      .then((list) => {
        setPresets(list);
        // Open on a real sketch with real bugs, not an empty form.
        const first = list.find((p) => p.id === "thermostat") ?? list[0];
        if (first) {
          load(first);
        }
      })
      .catch((e) => setError(`Could not load presets: ${e.message}`));
    // A finished run to open instantly, for anyone who does not want to wait ninety seconds.
    api
      .runs()
      .then((runs) => {
        const done = runs.filter((r) => r.mode === "break" && r.status === "fixed");
        setFinished(done.find((r) => /thermostat/i.test(r.title)) ?? done[0] ?? null);
      })
      .catch(() => undefined);
  }, []);

  const load = (p: Preset) => {
    setActive(p.id);
    setTitle(p.title);
    setFirmware(p.firmware);
    setPins(p.pins);
    setBehaviour(p.behaviour);
    setError("");
  };

  const start = async (override?: Preset) => {
    setBusy(true);
    setError("");
    try {
      const body = override ? { title: override.title, firmware: override.firmware, pins: override.pins, behaviour: override.behaviour } : { title, firmware, pins, behaviour };
      const { run_id } = await api.start({ mode: "break", ...body, compare });
      onStarted(run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <section className="panel grid gap-6 overflow-hidden p-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] lg:p-8">
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-halo">
            <Icon name="shield" /> Cast the bugs out of your firmware
          </div>
          <h1 className="mt-2 text-4xl font-semibold leading-[1.1] tracking-tight">Is your firmware possessed?</h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-muted">
            Hexorcist is an AI QA engineer. It runs your Arduino firmware on an emulated chip inside a sealed sandbox, shows measured proof of what breaks, then proves its own fix.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button className="btn-primary px-6 py-3 text-base" disabled={busy || !thermostat} onClick={() => thermostat && start(thermostat)}>
              <Icon name="play" /> {busy ? "Starting…" : "Try the thermostat"}
            </button>
            {finished && (
              <a href={`#/runs/${finished.id}`} className="btn-ghost px-4 py-3 text-[13px]">
                Open a finished run
              </a>
            )}
          </div>
          <p className="mt-2 text-[12px] text-faint">One click, nothing to paste. A full run takes about a minute and a half.</p>
          {error && <div className="mt-3 max-w-xl rounded-md border border-fail/40 bg-fail/10 px-3 py-2 text-[13px] text-fail">{error}</div>}
        </div>

        <div className="flex flex-col justify-center gap-3" aria-label="Why measured evidence beats reading code">
          <div className="rounded-lg border border-dashed border-line bg-raised/50 p-4">
            <div className="panel-title">An LLM reading the code</div>
            <p className="mt-1 text-[17px] italic leading-snug text-muted">“This might chatter.”</p>
          </div>
          <div className="rounded-lg border border-pass/40 bg-pass/5 p-4">
            <div className="panel-title !text-pass">Hexorcist running it</div>
            <p className="mt-1 font-mono text-[15px] leading-snug text-ink">D9 toggled 23 times in 5000 ms (limit 2)</p>
            <p className="mt-1 text-[13px] text-pass">Then it patches the sketch and re-runs everything: 1 toggle, all checks pass.</p>
          </div>
        </div>
      </section>

      <div className="flex items-baseline justify-between">
        <h2 className="panel-title">Or pick another example, or paste your own sketch</h2>
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
          <label className="flex cursor-pointer items-start gap-2 rounded-md border border-line bg-panel px-3 py-2 text-[12.5px] text-muted">
            <input type="checkbox" className="mt-0.5 accent-[#f0c05a]" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
            <span>
              <span className="text-ink">Also ask the LLM for a plain code review</span>, to show beside the measured results. One extra call, no emulator. Off by default.
            </span>
          </label>
          <button className="btn-primary w-full py-2.5" disabled={busy} onClick={() => start()}>
            {busy ? "Starting…" : "Cast the bugs out"}
          </button>
        </div>
      </div>
    </div>
  );
}
