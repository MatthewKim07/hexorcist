import { useEffect, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { api, PinSpec, Preset, RunSummary } from "../api";
import { PinTable } from "./PinTable";
import { Checkbox, Choices } from "./ui";

// The editor sits on the faceplate, so its colours stay quiet: graphite text, muted tints for syntax.
const editorTheme = [
  EditorView.theme({
    "&": { backgroundColor: "#EEF0EC", color: "#202427" },
    ".cm-content": { caretColor: "#202427", padding: "12px 0" },
    ".cm-cursor": { borderLeftColor: "#202427" },
    ".cm-gutters": { backgroundColor: "#EEF0EC", color: "#8A908B", border: "none" },
    ".cm-activeLine": { backgroundColor: "rgba(32, 36, 39, 0.035)" },
    ".cm-activeLineGutter": { backgroundColor: "transparent", color: "#5A615D" },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": { backgroundColor: "rgba(28, 104, 132, 0.18)" },
    ".cm-matchingBracket": { backgroundColor: "rgba(32, 36, 39, 0.08)", outline: "none" },
  }),
  syntaxHighlighting(
    HighlightStyle.define([
      { tag: [tags.keyword, tags.controlKeyword, tags.modifier, tags.processingInstruction], color: "#3D5663" },
      { tag: [tags.typeName, tags.standard(tags.typeName)], color: "#3D5663" },
      { tag: [tags.string, tags.character], color: "#55612F" },
      { tag: [tags.number, tags.bool, tags.null], color: "#7A4E22" },
      { tag: [tags.comment, tags.lineComment, tags.blockComment], color: "#646B67" },
      { tag: [tags.function(tags.variableName), tags.macroName], color: "#202427", fontWeight: "500" },
    ]),
  ),
];

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
        <h1 className="text-[48px] font-semibold leading-none tracking-[-0.03em]">Hexorcist</h1>
        <p className="mt-4 max-w-lg text-base text-muted">An AI QA engineer that breaks your firmware, then proves the fix.</p>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <button className="btn-primary" disabled={busy || !thermostat} onClick={() => thermostat && start(thermostat)}>
            {busy ? "Starting" : "Try the thermostat"}
          </button>
          <button className="btn-outline" onClick={toForm}>
            Paste your own firmware
          </button>
        </div>
        {error && <p className="mt-6 text-fail">{error}</p>}
      </section>

      <section id="paste" className="scroll-mt-20 border-t border-line pt-10">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <Choices
            label="Examples"
            options={presets.map((p) => ({ value: p.id, label: p.title }))}
            hints={Object.fromEntries(presets.map((p) => [p.id, p.summary]))}
            value={active}
            onChange={(id) => {
              const p = presets.find((x) => x.id === id);
              if (p) {
                load(p);
              }
            }}
          />
          {finished && (
            <a href={`#/runs/${finished.id}`} className="link text-sm">
              Open a finished run
            </a>
          )}
        </div>

        <div className="mt-8 grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <div>
            <div className="label mb-2">Sketch</div>
            <div className="h-[420px] overflow-hidden rounded-md border border-line bg-raised">
              <CodeMirror value={firmware} onChange={setFirmware} theme="none" extensions={[cpp(), ...editorTheme]} basicSetup={{ foldGutter: false, highlightActiveLineGutter: true }} height="420px" aria-label="Arduino sketch" />
            </div>
          </div>
          <div className="space-y-8">
            <div>
              <div className="label mb-2">Pins</div>
              <PinTable pins={pins} onChange={setPins} />
            </div>
            <div>
              <div className="label mb-2">Behaviour</div>
              <textarea aria-label="Intended behaviour" rows={7} className="field scroll resize-none leading-relaxed" value={behaviour} onChange={(e) => setBehaviour(e.target.value)} placeholder="What it must do, with numbers" />
            </div>
          </div>
        </div>

        {error && <p className="mt-6 text-fail">{error}</p>}
        <div className="mt-8 flex flex-wrap items-center gap-x-8 gap-y-4 pb-10">
          <button className="btn-primary" disabled={busy} onClick={() => start()}>
            {busy ? "Starting" : "Run"}
          </button>
          <Checkbox checked={compare} onChange={setCompare} className="text-sm text-muted" hint="One extra model call with no emulator, shown beside the measured results">
            Add a plain LLM review
          </Checkbox>
        </div>
      </section>
    </div>
  );
}
