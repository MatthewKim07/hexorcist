import { PinSpec, PinType } from "../api";
import { Icon } from "./Common";
import { Checkbox, Select } from "./ui";

const PINS = [...Array.from({ length: 14 }, (_, i) => `D${i}`), ...Array.from({ length: 6 }, (_, i) => `A${i}`)];
const TYPES: { value: PinType; label: string }[] = [
  { value: "analog_input", label: "Analog in" },
  { value: "digital_input", label: "Digital in" },
  { value: "digital_output", label: "Digital out" },
  { value: "pwm_output", label: "PWM out" },
];

export function PinTable({ pins, onChange }: { pins: PinSpec[]; onChange: (pins: PinSpec[]) => void }) {
  const update = (i: number, patch: Partial<PinSpec>) => onChange(pins.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  const free = PINS.find((p) => !pins.some((x) => x.pin === p) && p !== "D0" && p !== "D1") ?? "D2";

  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-[64px_minmax(0,1.3fr)_112px_minmax(0,1fr)_24px] gap-1.5 px-0.5 text-xs text-muted">
        <span>Pin</span>
        <span>Role</span>
        <span>Type</span>
        <span>Scale</span>
        <span />
      </div>
      {pins.map((p, i) => (
        <div key={i} className="grid grid-cols-[64px_minmax(0,1.3fr)_112px_minmax(0,1fr)_24px] items-center gap-1.5">
          <Select label={`Pin ${i + 1}`} mono className="px-2" value={p.pin} onChange={(v) => update(i, { pin: v })} options={PINS.map((name) => ({ value: name, label: name }))} />
          <input aria-label={`Role of ${p.pin}`} className="field h-9 py-0" placeholder="Temp sensor" value={p.role} onChange={(e) => update(i, { role: e.target.value })} />
          <Select label={`Type of ${p.pin}`} className="px-2" value={p.type} onChange={(v) => update(i, { type: v })} options={TYPES} />
          {p.type === "analog_input" ? (
            <input aria-label={`Scale of ${p.pin}`} className="field h-9 py-0 font-mono" placeholder="10 mV/°C" value={p.scale} onChange={(e) => update(i, { scale: e.target.value })} />
          ) : p.type === "digital_input" ? (
            <Checkbox checked={p.active_low} onChange={(v) => update(i, { active_low: v })} className="text-xs text-muted">
              Active low
            </Checkbox>
          ) : (
            <span />
          )}
          <button aria-label={`Remove ${p.pin}`} className="key h-6 w-6 rounded text-muted hover:text-fail" onClick={() => onChange(pins.filter((_, j) => j !== i))}>
            <Icon name="x" className="h-3 w-3" />
          </button>
        </div>
      ))}
      <button className="btn-ghost !px-0 mt-1" onClick={() => onChange([...pins, { pin: free, role: "", type: "digital_output", scale: "", active_low: false }])}>
        + Add pin
      </button>
    </div>
  );
}
