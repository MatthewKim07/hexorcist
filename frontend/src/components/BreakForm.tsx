import { useEffect, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import { tokyoNightInit } from "@uiw/codemirror-theme-tokyo-night";
import { tags } from "@lezer/highlight";
import { api, PinSpec, Preset, RunSummary } from "../api";
import { Icon } from "./Common";
import { PinTable } from "./PinTable";

// The stock theme's comments are too dim to read on a screen recording.
const editorTheme = tokyoNightInit({ settings: { background: "#151518", gutterBackground: "#151518" }, styles: [{ tag: [tags.comment, tags.lineComment, tags.blockComment], color: "#8b93a7" }] });

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

  const toForm = () => document.getElementById("paste")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div>
      <section className="flex min-h-[calc(100svh-57px-80px)] flex-col items-center justify-center py-12 text-center">
        <h1 className="text-[48px] font-semibold leading-none tracking-tight">Hexorcist</h1>
        <p className="mt-5 max-w-md text-[18px] text-muted">An AI QA engineer that breaks your firmware, then proves the fix.</p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <button className="btn-primary" disabled={busy || !thermostat} onClick={() => thermostat && start(thermostat)}>
            {busy ? "Starting…" : "Try the thermostat"}
          </button>
          <button className="btn-outline" onClick={toForm}>
            Paste your own firmware
          </button>
        </div>
        {error && <p className="mt-6 text-fail">{error}</p>}
        <p className="mt-10 flex items-center gap-3 text-[13px] text-faint">
          Attack <Icon name="arrow" className="h-3 w-3" /> Measure <Icon name="arrow" className="h-3 w-3" /> Fix
        </p>
      </section>

      <section id="paste" className="scroll-mt-20 border-t border-line pt-10">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="flex flex-wrap gap-x-5 gap-y-2" role="tablist" aria-label="Examples">
            {presets.map((p) => (
              <button key={p.id} role="tab" aria-selected={active === p.id} title={p.summary} onClick={() => load(p)} className={`-mb-px border-b-2 pb-1 text-[14px] transition-colors ${active === p.id ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink"}`}>
                {p.title}
              </button>
            ))}
          </div>
          {finished && (
            <a href={`#/runs/${finished.id}`} className="flex items-center gap-1.5 text-[14px] text-muted hover:text-ink">
              Open a finished run <Icon name="arrow" className="h-3 w-3" />
            </a>
          )}
        </div>

        <div className="mt-8 grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
          <div>
            <div className="label mb-2">Sketch</div>
            <div className="h-[420px] overflow-hidden rounded-md bg-raised">
              <CodeMirror value={firmware} onChange={setFirmware} theme={editorTheme} extensions={[cpp()]} height="420px" aria-label="Arduino sketch" />
            </div>
          </div>
          <div className="space-y-8">
            <div>
              <div className="label mb-2">Pins</div>
              <PinTable pins={pins} onChange={setPins} />
            </div>
            <div>
              <div className="label mb-2">Behaviour</div>
              <textarea aria-label="Intended behaviour" rows={6} className="field resize-y leading-relaxed" value={behaviour} onChange={(e) => setBehaviour(e.target.value)} placeholder="What it must do, with numbers" />
            </div>
          </div>
        </div>

        {error && <p className="mt-6 text-fail">{error}</p>}
        <div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-4 pb-10">
          <button className="btn-primary" disabled={busy} onClick={() => start()}>
            {busy ? "Starting…" : "Run"}
          </button>
          <label className="flex cursor-pointer items-center gap-2 text-[14px] text-muted" title="One extra LLM call, no emulator, shown beside the measured results">
            <input type="checkbox" className="accent-[#8b9bff]" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
            Add a plain LLM review
          </label>
        </div>
      </section>
    </div>
  );
}
