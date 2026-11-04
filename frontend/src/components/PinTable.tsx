import { PinSpec, PinType } from "../api";
import { Icon } from "./Common";

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
      <div className="grid grid-cols-[62px_minmax(0,1fr)_104px_minmax(0,1fr)_24px] gap-1.5 px-0.5 text-[11px] text-faint">
        <span>Pin</span>
        <span>Role</span>
        <span>Type</span>
        <span>Scale or wiring</span>
        <span />
      </div>
      {pins.map((p, i) => (
        <div key={i} className="grid grid-cols-[62px_minmax(0,1fr)_104px_minmax(0,1fr)_24px] items-center gap-1.5">
          <select aria-label="Pin" className="field px-1.5 font-mono" value={p.pin} onChange={(e) => update(i, { pin: e.target.value })}>
            {PINS.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
          <input aria-label="Role" className="field" placeholder="Temp sensor" value={p.role} onChange={(e) => update(i, { role: e.target.value })} />
          <select aria-label="Type" className="field px-1.5" value={p.type} onChange={(e) => update(i, { type: e.target.value as PinType })}>
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          {p.type === "analog_input" ? (
            <input aria-label="Scale" className="field font-mono" placeholder="10 mV/°C" value={p.scale} onChange={(e) => update(i, { scale: e.target.value })} />
          ) : p.type === "digital_input" ? (
            <label className="flex items-center gap-1.5 text-[12px] text-muted">
              <input type="checkbox" className="accent-[#f0c05a]" checked={p.active_low} onChange={(e) => update(i, { active_low: e.target.checked })} />
              Active LOW
            </label>
          ) : (
            <span />
          )}
          <button aria-label={`Remove ${p.pin}`} className="flex h-6 w-6 items-center justify-center rounded text-faint hover:bg-raised hover:text-fail" onClick={() => onChange(pins.filter((_, j) => j !== i))}>
            <Icon name="x" className="h-3 w-3" />
          </button>
        </div>
      ))}
      <button className="btn-ghost mt-1" onClick={() => onChange([...pins, { pin: free, role: "", type: "digital_output", scale: "", active_low: false }])}>
        + Add pin
      </button>
    </div>
  );
}
