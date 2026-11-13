import { useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { cpp } from "@codemirror/lang-cpp";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView, placeholder } from "@codemirror/view";
import { tags } from "@lezer/highlight";
import * as RDialog from "@radix-ui/react-dialog";
import { Check, PinSpec, PinType, Preset } from "../api";
import { chipLabel, fieldsOf, readField, withField } from "../checks";
import { lineCount, sketchName } from "../sketch";
import { Checkbox, Select } from "./ui";

const TYPES: { value: PinType; label: string }[] = [
  { value: "digital_output", label: "Digital out" },
  { value: "pwm_output", label: "PWM out" },
  { value: "digital_input", label: "Digital in" },
  { value: "analog_input", label: "Analog in" },
];

/** Wiring for one header pin: what is connected and how to read it. Edits to a wired pin apply as you type. */
export function PinEditor({ pin, current, guess, onChange, onRemove, onClose }: { pin: string; current?: PinSpec; guess?: { type: PinType; active_low: boolean }; onChange: (p: PinSpec) => void; onRemove: () => void; onClose: () => void }) {
  const analogOnly = pin.startsWith("A");
  const [draft, setDraft] = useState<PinSpec>(current ?? { pin, role: "", type: analogOnly ? "analog_input" : guess?.type ?? "digital_output", scale: "", active_low: guess?.active_low ?? false });
  const update = (patch: Partial<PinSpec>) => {
    const next = { ...draft, ...patch };
    setDraft(next);
    if (current) {
      onChange(next);
    }
  };
  const types = analogOnly ? TYPES.filter((t) => t.value === "analog_input" || t.value === "digital_input") : TYPES.filter((t) => t.value !== "analog_input");
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!current) {
          onChange(draft);
        }
        onClose();
      }}
    >
      <p className="flex items-baseline justify-between">
        <span className="font-medium">
          <span className="font-mono">{pin}</span> {current ? "" : "is free"}
        </span>
        {(pin === "D0" || pin === "D1") && <span className="text-xs text-muted">Carries the serial line</span>}
      </p>
      <label className="block">
        <span className="label mb-1 block">What is connected</span>
        <input autoFocus className="field" placeholder="Fan, push button, LM35 sensor" value={draft.role} onChange={(e) => update({ role: e.target.value })} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <span className="label mb-1 block">Signal</span>
          <Select label={`Signal on ${pin}`} value={draft.type} onChange={(v) => update({ type: v })} options={types} className="w-full" />
        </div>
        {draft.type === "analog_input" && (
          <label className="block">
            <span className="label mb-1 block">Scale</span>
            <input className="field num h-9 !py-0" placeholder="10 mV/°C" value={draft.scale} onChange={(e) => update({ scale: e.target.value })} />
          </label>
        )}
        {draft.type === "digital_input" && (
          <div className="flex items-end pb-2">
            <Checkbox checked={draft.active_low} onChange={(v) => update({ active_low: v })} className="text-sm">
              Active low
            </Checkbox>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between pt-1">
        {current ? (
          <button type="button" className="btn-ghost !px-0 hover:!text-fail" onClick={onRemove}>
            Unwire {pin}
          </button>
        ) : (
          <span />
        )}
        <button type="submit" className={current ? "btn-outline !py-1.5" : "btn-primary !py-1.5"}>
          {current ? "Done" : `Wire ${pin}`}
        </button>
      </div>
    </form>
  );
}

/** One check: what it measures, the numbers that can be changed, and a way to drop it. */
export function CheckEditor({ check, pins, onChange, onRemove, onClose }: { check: Check; pins: PinSpec[]; onChange: (c: Check) => void; onRemove: () => void; onClose: () => void }) {
  const fields = fieldsOf(check, pins);
  return (
    <div className="space-y-3">
      <p className="font-medium">{chipLabel(check, pins)}</p>
      {check.description && <p className="text-xs text-muted">{check.description}</p>}
      {fields.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {fields.map((f) => (
            <label key={f.path.join(".")} className="block">
              <span className="label mb-1 block">{f.label}</span>
              <span className="flex items-center gap-1.5">
                <input
                  type="number"
                  min={0}
                  step="any"
                  className="field num h-9 !py-0"
                  value={readField(check, f.path)}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    if (Number.isFinite(v) && v >= 0) {
                      onChange(withField(check, f.path, v, pins));
                    }
                  }}
                />
                <span className="shrink-0 text-xs text-muted">{f.unit}</span>
              </span>
            </label>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between pt-1">
        <button type="button" className="btn-ghost !px-0 hover:!text-fail" onClick={onRemove}>
          Drop this check
        </button>
        <button type="button" className="btn-outline !py-1.5" onClick={onClose}>
          Done
        </button>
      </div>
    </div>
  );
}

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
    ".cm-placeholder": { color: "#8A908B" },
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
  placeholder("void setup()\n{\n  pinMode(9, OUTPUT);\n}\n\nvoid loop()\n{\n}"),
];

/** The sketch, in a sheet from the right. Opens by itself while there is no sketch yet. */
export function SketchSheet({ open, onOpenChange, firmware, onFirmware, presets, onPreset }: { open: boolean; onOpenChange: (v: boolean) => void; firmware: string; onFirmware: (v: string) => void; presets: Preset[]; onPreset: (p: Preset) => void }) {
  const empty = !firmware.trim();
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="scrim fixed inset-0 z-40 bg-[#121816]/25" />
        <RDialog.Content className="drawer fixed inset-y-0 right-0 z-50 flex w-[min(760px,100vw)] flex-col border-l border-line bg-bg shadow-[-12px_0_32px_rgba(18,24,22,0.12)] outline-none" onOpenAutoFocus={(e) => e.preventDefault()}>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-5 py-4">
            <RDialog.Title className="text-base font-semibold">{empty ? "Paste your sketch" : sketchName(firmware)}</RDialog.Title>
            <span className="num text-xs text-muted">{empty ? "" : `${lineCount(firmware)} lines`}</span>
            <RDialog.Close className="btn-outline ml-auto !py-1.5">{empty ? "Close" : "Done"}</RDialog.Close>
          </div>
          <RDialog.Description className={empty ? "px-5 pt-4 text-sm text-muted" : "sr-only"}>
            {empty ? "Paste an Arduino Uno sketch into the editor, or start from an example. It compiles and runs only inside a sealed sandbox." : "The Arduino sketch under test."}
          </RDialog.Description>
          {empty && presets.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 px-5 pt-3">
              {presets.map((p) => (
                <button key={p.id} className="key rounded-full border border-line bg-raised px-3 py-1 text-xs !font-normal text-muted hover:text-ink" onClick={() => onPreset(p)}>
                  {p.title}
                </button>
              ))}
            </div>
          )}
          <div className="m-5 min-h-0 flex-1 overflow-hidden rounded-md border border-line bg-raised">
            <CodeMirror autoFocus value={firmware} onChange={onFirmware} theme="none" extensions={[cpp(), ...editorTheme]} basicSetup={{ foldGutter: false, highlightActiveLineGutter: true }} height="100%" className="h-full" aria-label="Arduino sketch" />
          </div>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}
