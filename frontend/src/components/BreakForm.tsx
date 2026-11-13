import { useEffect, useMemo, useState } from "react";
import { api, Check, DeviceModel, Health, PinSpec, Preset } from "../api";
import { ms } from "../checks";
import { lineCount, mentionedPins, sketchName } from "../sketch";
import { BoardStage, StageChip } from "./BoardStage";
import { useStripText } from "./Chassis";
import { CheckEditor, PinEditor, SketchSheet } from "./SetupEditors";
import { Checkbox, Fold, KeyRow } from "./ui";

type Panel = "firmware" | "wiring" | "checks";
type Source = "example" | "preview";

/** What the checks were read from. A run may reuse them only while the text and wiring still match. */
interface ReadFrom {
  behaviour: string;
  wiring: string;
  firmware: string;
}

interface Setup {
  preset: string | null;
  title: string;
  firmware: string;
  pins: PinSpec[];
  behaviour: string;
  checks: Check[] | null;
  source: Source | null;
  deviceModel: DeviceModel | null;
  readFrom: ReadFrom | null;
  readBy: string;
}

const EMPTY: Setup = { preset: null, title: "", firmware: "", pins: [], behaviour: "", checks: null, source: null, deviceModel: null, readFrom: null, readBy: "" };
const STORE = "hexorcist.setup";
const TYPE_NAMES: Record<string, string> = { digital_output: "digital out", pwm_output: "PWM out", digital_input: "digital in", analog_input: "analog in" };

/** The wiring as the checks see it. Renaming a part changes no measurement, so roles are left out. */
function wiringKey(pins: PinSpec[]): string {
  return JSON.stringify([...pins].sort((a, b) => a.pin.localeCompare(b.pin)).map((p) => [p.pin, p.type, p.scale, p.active_low]));
}

function restore(): Setup {
  try {
    const saved = sessionStorage.getItem(STORE);
    return saved ? { ...EMPTY, ...JSON.parse(saved) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

function listOf(items: string[]): string {
  return items.length <= 1 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function BreakForm({ health, onStarted }: { health: Health | null; onStarted: (id: string) => void }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [s, setS] = useState<Setup>(restore);
  const [panel, setPanel] = useState<Panel | null>("firmware");
  const [sheet, setSheet] = useState(() => !restore().firmware.trim());
  const [list, setList] = useState(false);
  const [compare, setCompare] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [previewError, setPreviewError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const patch = (p: Partial<Setup>) => setS((prev) => ({ ...prev, ...p }));

  useEffect(() => {
    api
      .presets()
      .then(setPresets)
      .catch((e) => setError(`Could not load the examples: ${e.message}`));
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORE, JSON.stringify(s));
    } catch {
      // Private windows can refuse storage. The setup still works for this visit.
    }
  }, [s]);

  const hasSketch = !!s.firmware.trim();
  const fresh = !!s.checks && !!s.readFrom && s.readFrom.behaviour === s.behaviour && s.readFrom.wiring === wiringKey(s.pins);
  const sameSketch = fresh && s.readFrom!.firmware === s.firmware;
  const shown = (s.checks ?? []).filter((c) => c.type !== "no_crash");
  const llm = health?.llm_configured ?? true;
  const canRun = hasSketch && !!s.behaviour.trim() && llm && !busy;
  const mentioned = useMemo(() => mentionedPins(s.firmware), [s.firmware]);
  const unwired = mentioned.filter((m) => !s.pins.some((p) => p.pin === m.pin));

  useStripText(busy ? "Starting" : !hasSketch ? "Paste a sketch" : !s.behaviour.trim() ? "Say what it must do" : !llm ? "No model" : "Ready");

  const load = (p: Preset) => {
    setS({
      preset: p.id,
      title: p.title,
      firmware: p.firmware,
      pins: p.pins,
      behaviour: p.behaviour,
      checks: p.checks?.assertions ?? null,
      source: p.checks ? "example" : null,
      deviceModel: p.checks?.device_model ?? null,
      readFrom: p.checks ? { behaviour: p.behaviour, wiring: wiringKey(p.pins), firmware: p.firmware } : null,
      readBy: "",
    });
    setWarnings([]);
    setPreviewError("");
    setError("");
    setSheet(false);
  };

  const preview = async () => {
    setPreviewing(true);
    setPreviewError("");
    try {
      const got = await api.previewChecks({ firmware: s.firmware, pins: s.pins, behaviour: s.behaviour });
      patch({ checks: got.assertions, source: "preview", deviceModel: got.device_model, readFrom: { behaviour: s.behaviour, wiring: wiringKey(s.pins), firmware: s.firmware }, readBy: `${got.model} in ${ms(got.duration_ms)}` });
      setWarnings(got.warnings);
    } catch (e) {
      setPreviewError((e as Error).message);
    } finally {
      setPreviewing(false);
    }
  };

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const checks = fresh ? { assertions: s.checks, device_model: sameSketch ? s.deviceModel : null, source: s.source } : undefined;
      const title = s.preset && s.firmware === presets.find((p) => p.id === s.preset)?.firmware ? s.title : "";
      const { run_id } = await api.start({ mode: "break", title, firmware: s.firmware, pins: s.pins, behaviour: s.behaviour, compare, ...(checks ? { checks } : {}) });
      onStarted(run_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const setPin = (next: PinSpec) => patch({ pins: s.pins.some((p) => p.pin === next.pin) ? s.pins.map((p) => (p.pin === next.pin ? next : p)) : [...s.pins, next] });
  const dropPin = (pin: string) => patch({ pins: s.pins.filter((p) => p.pin !== pin) });
  const keyOf = (c: Check, i: number) => c.id ?? `c${i}`;
  const setCheck = (key: string, next: Check | null) => patch({ checks: (s.checks ?? []).flatMap((c, i) => (keyOf(c, i) === key ? (next ? [next] : []) : [c])) });

  const chips: StageChip[] = (s.checks ?? []).flatMap((c, i) => (c.type === "no_crash" ? [] : [{ key: keyOf(c, i), check: c, tone: fresh ? "idle" : "off", status: fresh ? undefined : "out of date" }]));

  const examples = presets.length > 0 && (
    <div className="flex flex-wrap items-center gap-2">
      <span className="label mr-1">Load an example</span>
      {presets.map((p) => (
        <button key={p.id} aria-pressed={s.preset === p.id} className="key rounded-full border border-line bg-raised px-3 py-1 text-xs !font-normal text-muted hover:text-ink aria-pressed:border-ink aria-pressed:text-ink" onClick={() => load(p)} title={p.summary}>
          {p.title}
        </button>
      ))}
    </div>
  );

  const behaviourField = (
    <textarea aria-label="What the sketch must do" rows={5} className="field scroll resize-y leading-relaxed" value={s.behaviour} onChange={(e) => patch({ behaviour: e.target.value })} placeholder="What it must do, with numbers. For example: the fan turns on at 30 °C and off at 27 °C, and switches at most twice in any 5 seconds." />
  );

  return (
    <div className="space-y-5">
      <section aria-label="Bench" className="screen rounded-xl border border-[#0b0f0e] bg-screen">
        <div className="flex items-center gap-3 px-4 pt-3 text-xs">
          <span className="font-mono text-screen-muted">{s.title && s.preset ? s.title : hasSketch ? sketchName(s.firmware) : "No sketch"}</span>
          <span className="text-screen-muted/70">
            {s.pins.length} wired · {shown.length} check{shown.length === 1 ? "" : "s"}
          </span>
          <button type="button" aria-pressed={list} aria-label="List view" onClick={() => setList((v) => !v)} className="key ml-auto rounded-full border border-screen-line px-2.5 py-1 !font-normal text-screen-muted hover:text-screen-ink aria-pressed:border-screen-muted aria-pressed:text-screen-ink">
            List
          </button>
        </div>
        <BoardStage
          pins={s.pins}
          trace={null}
          t={0}
          chips={chips}
          list={list}
          className="mx-auto max-w-[960px] pb-2"
          sketch={{ label: hasSketch ? sketchName(s.firmware) : "sketch.ino", empty: !hasSketch, onOpen: () => setSheet(true) }}
          pinPopover={(pin, close) => {
            const m = mentioned.find((x) => x.pin === pin);
            return <PinEditor key={pin} pin={pin} current={s.pins.find((p) => p.pin === pin)} guess={m} onChange={setPin} onRemove={() => (dropPin(pin), close())} onClose={close} />;
          }}
          chipPopover={(chip, close) => <CheckEditor check={chip.check} pins={s.pins} onChange={(c) => setCheck(chip.key, c)} onRemove={() => (setCheck(chip.key, null), close())} onClose={close} />}
        />
      </section>

      <KeyRow
        label="Setup"
        value={panel}
        onChange={setPanel}
        onPress={(v, wasOpen) => v === "firmware" && wasOpen && setSheet(true)}
        keys={[
          { value: "firmware", label: "Firmware", lamp: hasSketch },
          { value: "wiring", label: "Wiring", lamp: s.pins.length > 0 },
          { value: "checks", label: "Checks", lamp: fresh && shown.length > 0 },
        ]}
        end={
          <>
            <Checkbox checked={compare} onChange={setCompare} className="text-sm text-muted" hint="Extra guess with no emulator, shown next to the measured results">
              Also ask the model
            </Checkbox>
            <button className="btn-primary" disabled={!canRun} onClick={start}>
              {busy ? "Starting" : "Run"}
            </button>
          </>
        }
      >
        <div className="mt-4 rounded-lg border border-line bg-raised/60 p-5 text-sm">
          {panel === "firmware" && (
            <div className="space-y-5">
              {hasSketch ? (
                <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                  <div>
                    <p className="font-mono">{sketchName(s.firmware)}</p>
                    <p className="mt-0.5 text-muted">
                      {lineCount(s.firmware)} lines{mentioned.length > 0 ? `, uses ${listOf(mentioned.map((m) => m.pin))}` : ""}
                    </p>
                  </div>
                  <button className="btn-outline" onClick={() => setSheet(true)}>
                    Open the sketch
                  </button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                  <p className="text-muted">No sketch yet.</p>
                  <button className="btn-primary" onClick={() => setSheet(true)}>
                    Paste a sketch
                  </button>
                </div>
              )}
              {examples}
            </div>
          )}

          {panel === "wiring" && (
            <div className="space-y-4">
              <p className="text-muted">Tap a pin on the board to wire it.</p>
              {unwired.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mr-1">The sketch uses {listOf(unwired.map((m) => m.pin))}:</span>
                  {unwired.map((m) => (
                    <button key={m.pin} className="btn-outline !py-1.5 text-xs" onClick={() => setPin({ pin: m.pin, role: "", type: m.type, scale: "", active_low: m.active_low })}>
                      Wire {m.pin} as {TYPE_NAMES[m.type]}
                    </button>
                  ))}
                </div>
              )}
              {s.pins.length > 0 && (
                <ul className="divide-y divide-line border-y border-line">
                  {s.pins.map((p) => (
                    <li key={p.pin} className="flex items-baseline gap-4 py-2">
                      <span className="w-8 font-mono">{p.pin}</span>
                      <span className="min-w-0 flex-1 truncate">{p.role || <span className="text-muted">unnamed</span>}</span>
                      <span className="text-muted">
                        {TYPE_NAMES[p.type]}
                        {p.scale ? `, ${p.scale}` : ""}
                        {p.active_low ? ", active low" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {panel === "checks" && (
            <div className="space-y-4">
              {s.checks && fresh && (
                <p className="text-muted">
                  {s.source === "example" ? `${shown.length} checks from the example.` : `${shown.length} from your text · ${s.readBy}.`} Tap a chip to edit.
                </p>
              )}
              {s.checks && !fresh && <p>Text changed. Preview again, or run and they will be read during the run.</p>}
              {!s.checks && <p className="text-muted">Say what it must do, with numbers. Then preview the checks.</p>}
              {warnings.length > 0 && fresh && (
                <ul className="space-y-1 text-muted">
                  {warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
              {s.checks ? (
                <Fold title="Edit the full text" defaultOpen={!fresh}>
                  {behaviourField}
                </Fold>
              ) : (
                behaviourField
              )}
              {(!s.checks || !fresh || s.source === "preview") && (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  <button className="btn-outline" disabled={!s.behaviour.trim() || previewing || !llm} onClick={preview}>
                    {previewing ? "Reading the text" : fresh ? "Preview checks again" : "Preview checks"}
                  </button>
                  <span className="text-xs text-muted">One model call. Nothing runs yet.</span>
                </div>
              )}
              {previewError && <p className="text-fail">{previewError}</p>}
            </div>
          )}
        </div>
      </KeyRow>

      {error && <p className="text-fail">{error}</p>}

      <SketchSheet open={sheet} onOpenChange={setSheet} firmware={s.firmware} onFirmware={(v) => patch({ firmware: v })} presets={presets} onPreset={load} />
    </div>
  );
}
