import { useMemo } from "react";
import { PinSpec, Scenario, Trace } from "../api";
import { AnalogTrack, Component, componentFor, InputTrack, OutputTrack, parseScale, PIN_COLORS, toPhysical } from "../trace";

const W = 960;
const H = 500;
const TOP_Y = 112;
const BOTTOM_Y = 388;

function pinXY(pin: string): { x: number; y: number } {
  const n = parseInt(pin.slice(1), 10);
  if (pin.startsWith("A")) {
    return { x: 512 + n * 20, y: 352 };
  }
  // The Uno's digital header runs D13 on the left to D0 on the right, with a gap after D8.
  return n >= 8 ? { x: 368 + (13 - n) * 20, y: 148 } : { x: 496 + (7 - n) * 20, y: 148 };
}

interface Live {
  pin: PinSpec;
  color: string;
  component: Component;
  level: number;
  brightness: number;
  toggles: number;
  angle: number;
  value: number;
  mv: number;
  unit: string;
  range: [number, number];
  floating: boolean;
  pressed: boolean;
}

function niceRange(lo: number, hi: number): [number, number] {
  if (!isFinite(lo) || !isFinite(hi)) {
    return [0, 100];
  }
  const span = Math.max(hi - lo, 1);
  const step = Math.pow(10, Math.floor(Math.log10(span)));
  return [Math.floor(lo / step - 0.5) * step, Math.ceil(hi / step + 0.5) * step];
}

export function VirtualBoard({ pins, trace, t, scenario, tag }: { pins: PinSpec[]; trace: Trace | null; t: number; scenario?: Scenario; tag?: string }) {
  const tracks = useMemo(() => {
    if (!trace) {
      return null;
    }
    return pins.map((pin) => {
      if (pin.type === "analog_input") {
        const analog = new AnalogTrack(trace, pin.pin);
        const scale = parseScale(pin.scale);
        const lo = analog.empty ? 0 : toPhysical(Math.min(...analog.low), scale);
        const hi = analog.empty ? 100 : toPhysical(Math.max(...analog.high), scale);
        return { kind: "analog" as const, analog, scale, range: niceRange(Math.min(lo, hi), Math.max(lo, hi)) };
      }
      if (pin.type === "digital_input") {
        const initial = scenario?.digital?.find((d) => d.pin === pin.pin)?.initial ?? (pin.active_low ? 1 : 0);
        return { kind: "input" as const, input: new InputTrack(trace, pin.pin, initial) };
      }
      return { kind: "output" as const, output: new OutputTrack(trace, pin.pin) };
    });
  }, [trace, pins, scenario]);

  const live: Live[] = pins.map((pin, i) => {
    const base: Live = { pin, color: PIN_COLORS[i % PIN_COLORS.length], component: componentFor(pin), level: 0, brightness: 0, toggles: 0, angle: 0, value: 0, mv: 0, unit: "", range: [0, 100], floating: false, pressed: false };
    const track = tracks?.[i];
    base.floating = !!scenario?.floating?.some((w) => w.pin === pin.pin && t >= w.from_ms && t < w.to_ms);
    if (!track) {
      return base;
    }
    if (track.kind === "analog") {
      base.mv = track.analog.at(t);
      base.value = toPhysical(base.mv, track.scale);
      base.unit = track.scale.unit;
      base.range = track.range;
    } else if (track.kind === "input") {
      base.level = track.input.at(t);
      base.pressed = pin.active_low ? base.level === 0 : base.level === 1;
    } else {
      base.level = track.output.levelAt(t);
      base.brightness = track.output.brightnessAt(t);
      base.toggles = track.output.togglesUntil(t);
      base.angle = (track.output.highTimeUntil(t) * 0.9) % 360;
    }
    return base;
  });

  const place = (items: Live[], y: number) => {
    const sorted = [...items].sort((a, b) => pinXY(a.pin.pin).x - pinXY(b.pin.pin).x);
    const gap = Math.min(170, (W - 60) / Math.max(sorted.length, 1));
    const left = W / 2 - (gap * (sorted.length - 1)) / 2;
    return sorted.map((item, i) => ({ item, x: left + gap * i, y }));
  };
  const top = place(live.filter((l) => l.pin.type !== "analog_input"), TOP_Y);
  const bottom = place(live.filter((l) => l.pin.type === "analog_input"), BOTTOM_Y);
  const viewH = bottom.length ? H : 410;
  const slots = [...top, ...bottom].map((s) => s.x);
  const viewLeft = Math.max(0, Math.min(190, ...slots.map((x) => x - 100)));
  const viewRight = Math.min(W, Math.max(W - 190, ...slots.map((x) => x + 100)));
  const lineNow = !!trace?.serial_log.some((l) => l.t_ms <= t && t - l.t_ms < 60);
  const d13 = live.find((l) => l.pin.pin === "D13");

  return (
    <svg viewBox={`${viewLeft} 0 ${viewRight - viewLeft} ${viewH}`} className="mx-auto block max-h-[520px] w-full" role="img" aria-label={`Replay of the Arduino Uno. ${live.map((l) => describe(l)).join(". ")}`}>
      <defs>
        <linearGradient id="pcb" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0f4c5c" />
          <stop offset="1" stopColor="#0a3644" />
        </linearGradient>
        <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id="ledGlow">
          <stop offset="0" stopColor="#ffd98a" stopOpacity="0.95" />
          <stop offset="1" stopColor="#f0c05a" stopOpacity="0" />
        </radialGradient>
      </defs>

      {[...top, ...bottom].map(({ item, x, y }) => {
        const p = pinXY(item.pin.pin);
        const isTop = y === TOP_Y;
        const active = item.pin.type.endsWith("output") ? item.level === 1 : item.pin.type === "digital_input" ? item.pressed : true;
        const d = isTop ? `M ${p.x} ${p.y} C ${p.x} ${p.y - 34}, ${x} ${y + 40}, ${x} ${y}` : `M ${p.x} ${p.y} C ${p.x} ${p.y + 34}, ${x} ${y - 40}, ${x} ${y}`;
        return <path key={item.pin.pin} d={d} fill="none" stroke={item.color} strokeWidth="2.2" strokeLinecap="round" opacity={active ? 1 : 0.38} filter={active && item.pin.type.endsWith("output") ? "url(#glow)" : undefined} />;
      })}

      <Board live={live} lineNow={lineNow} d13On={d13?.level === 1 && d13.pin.type.endsWith("output")} />

      {top.map(({ item, x }) => (
        <g key={item.pin.pin} transform={`translate(${x}, 0)`}>
          <Part item={item} />
        </g>
      ))}
      {bottom.map(({ item, x }) => (
        <g key={item.pin.pin} transform={`translate(${x}, ${BOTTOM_Y})`}>
          <Gauge item={item} />
        </g>
      ))}

      {tag && (
        <g transform={`translate(${viewLeft + 8}, ${viewH - 32})`}>
          <rect width="104" height="22" rx="4" fill="#181c25" stroke="#262b36" />
          <text x="52" y="15" textAnchor="middle" fontSize="11" fontFamily="IBM Plex Mono" fill="#e7e9ee">
            {tag}
          </text>
        </g>
      )}
      <text x={viewRight - 8} y={viewH - 16} textAnchor="end" fontSize="16" fontFamily="IBM Plex Mono" fill="#e7e9ee">
        t = {(t / 1000).toFixed(2)} s
      </text>
    </svg>
  );
}

function describe(l: Live): string {
  if (l.pin.type === "analog_input") {
    return `${l.pin.pin} ${l.pin.role} ${l.value.toFixed(1)} ${l.unit}`;
  }
  if (l.pin.type === "digital_input") {
    return `${l.pin.pin} ${l.pin.role} ${l.pressed ? "pressed" : "released"}`;
  }
  return `${l.pin.pin} ${l.pin.role} ${l.level ? "on" : "off"}`;
}

function Board({ live, lineNow, d13On }: { live: Live[]; lineNow: boolean; d13On: boolean }) {
  const used = new Map(live.map((l) => [l.pin.pin, l]));
  const digital = Array.from({ length: 14 }, (_, n) => `D${n}`);
  const analog = Array.from({ length: 6 }, (_, n) => `A${n}`);
  const header = (pin: string) => {
    const { x, y } = pinXY(pin);
    const u = used.get(pin);
    const lit = u && (u.pin.type.endsWith("output") ? u.level === 1 : u.pin.type === "digital_input" ? u.pressed : true);
    return (
      <g key={pin}>
        <rect x={x - 6} y={y - 6} width="12" height="12" fill="#0a0c10" />
        <circle cx={x} cy={y} r={u ? 3.6 : 2.2} fill={u ? u.color : "#8a7a4a"} opacity={u && !lit ? 0.6 : 1} />
        <text x={x} y={pin.startsWith("A") ? y - 11 : y + 19} textAnchor="middle" fontSize="8.5" fontFamily="IBM Plex Mono" fill={u ? "#e7e9ee" : "#7fb3bf"}>
          {pin.slice(pin.startsWith("A") ? 0 : 1)}
        </text>
      </g>
    );
  };
  return (
    <g>
      <rect x="290" y="130" width="380" height="240" rx="10" fill="url(#pcb)" stroke="#1b6a7d" />
      {[[304, 144], [656, 150], [304, 356], [656, 356]].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="5" fill="#0b0d12" stroke="#c9b26a" strokeWidth="1.5" />
      ))}
      <rect x="262" y="170" width="74" height="52" rx="3" fill="#aeb4bd" stroke="#6d737c" />
      <rect x="268" y="178" width="30" height="36" fill="#7f858e" />
      <rect x="266" y="296" width="62" height="50" rx="4" fill="#15171c" stroke="#2a2d34" />
      <circle cx="288" cy="321" r="11" fill="#0b0d12" stroke="#2a2d34" />
      <rect x="354" y="138" width="124" height="20" rx="1" fill="#0a0c10" />
      <rect x="484" y="138" width="170" height="20" rx="1" fill="#0a0c10" />
      <rect x="500" y="342" width="144" height="20" rx="1" fill="#0a0c10" />
      <rect x="350" y="342" width="136" height="20" rx="1" fill="#0a0c10" />
      <text x="418" y="337" textAnchor="middle" fontSize="8.5" fontFamily="IBM Plex Mono" fill="#7fb3bf">POWER</text>
      {digital.map(header)}
      {analog.map(header)}

      <rect x="420" y="268" width="180" height="46" rx="3" fill="#15171c" stroke="#2a2d34" />
      {Array.from({ length: 14 }).map((_, i) => (
        <g key={i}>
          <rect x={426 + i * 12.3} y="263" width="5" height="5" fill="#b8bcc4" />
          <rect x={426 + i * 12.3} y="314" width="5" height="5" fill="#b8bcc4" />
        </g>
      ))}
      <text x="510" y="295" textAnchor="middle" fontSize="12" fontFamily="IBM Plex Mono" fill="#aeb4bd">ATmega328P</text>
      <rect x="366" y="272" width="34" height="14" rx="6" fill="#c8ccd3" />

      <g transform="translate(360, 182)">
        <circle cx="4" cy="4" r="4" fill={d13On ? "#ffcf6e" : "#3a3f2a"} filter={d13On ? "url(#glow)" : undefined} />
        <text x="13" y="7.5" fontSize="8.5" fontFamily="IBM Plex Mono" fill="#7fb3bf">L</text>
        <circle cx="4" cy="20" r="4" fill={lineNow ? "#ffcf6e" : "#3a3f2a"} filter={lineNow ? "url(#glow)" : undefined} />
        <text x="13" y="23.5" fontSize="8.5" fontFamily="IBM Plex Mono" fill="#7fb3bf">TX</text>
      </g>

      <g transform="translate(476, 196)">
        <ellipse cx="0" cy="-12" rx="11" ry="3.6" fill="none" stroke="#f0c05a" strokeWidth="1.6" />
        <text x="18" y="-6" fontSize="15" fontWeight="600" fontFamily="IBM Plex Sans" fill="#cfe6ec" letterSpacing="1.5">HEXORCIST</text>
        <text x="18" y="9" fontSize="9" fontFamily="IBM Plex Mono" fill="#7fb3bf">UNO, EMULATED AT 16 MHZ</text>
        <rect x="-9" y="-6" width="18" height="16" rx="1.5" fill="none" stroke="#cfe6ec" strokeWidth="1.2" />
      </g>
    </g>
  );
}

function Caption({ item, state, y = 8 }: { item: Live; state?: string; y?: number }) {
  return (
    <>
      <text textAnchor="middle" y={y} fontSize="11" fontFamily="IBM Plex Sans" fontWeight="500" fill="#e7e9ee">
        {item.pin.pin} {shorten(item.pin.role)}
      </text>
      {state && (
        <text textAnchor="middle" y={y + 13} fontSize="10" fontFamily="IBM Plex Mono" fill="#a2a9b6">
          {state}
        </text>
      )}
    </>
  );
}

function shorten(role: string): string {
  const clean = role.replace(/\s*\(.*\)/, "");
  return clean.length > 20 ? `${clean.slice(0, 19)}…` : clean;
}

function Part({ item }: { item: Live }) {
  const toggles = `${item.toggles} toggle${item.toggles === 1 ? "" : "s"}`;
  if (item.component === "button" || item.component === "switch") {
    const label = item.floating ? "FLOATING" : item.pressed ? "PRESSED" : "RELEASED";
    return (
      <g>
        <Caption item={item} state={label} y={12} />
        <rect x="-26" y="68" width="52" height="30" rx="4" fill="#20242e" stroke="#3a4050" />
        <rect x="-16" y={item.pressed ? 62 : 52} width="32" height={item.pressed ? 12 : 22} rx="4" fill={item.floating ? "#e8a33d" : item.pressed ? "#f0c05a" : "#59606f"} stroke="#0b0d12" filter={item.pressed ? "url(#glow)" : undefined} />
        <line x1="0" y1="98" x2="0" y2="112" stroke={item.color} strokeWidth="2.2" />
      </g>
    );
  }
  if (item.component === "fan") {
    const on = item.level === 1;
    return (
      <g>
        <Caption item={item} state={`${on ? "ON" : "OFF"}  ${toggles}`} y={10} />
        <circle cy="66" r="34" fill="#181c25" stroke={on ? "#f0c05a" : "#3a4050"} strokeWidth="2" filter={on ? "url(#glow)" : undefined} />
        <g transform={`translate(0, 66) rotate(${item.angle})`}>
          {[0, 120, 240].map((a) => (
            <path key={a} transform={`rotate(${a})`} d="M0 -5 C 12 -25, 25 -18, 22 -6 C 19 -1, 8 -1, 0 -5 Z" fill={on ? "#f0c05a" : "#59606f"} />
          ))}
          <circle r="5" fill="#0b0d12" stroke={on ? "#f0c05a" : "#59606f"} strokeWidth="1.5" />
        </g>
      </g>
    );
  }
  if (item.component === "siren") {
    const on = item.level === 1;
    return (
      <g>
        <Caption item={item} state={`${on ? "SOUNDING" : "SILENT"}  ${toggles}`} y={10} />
        <path d="M-22 56 h12 l20 -16 v52 l-20 -16 h-12 Z" fill={on ? "#f0c05a" : "#59606f"} stroke="#0b0d12" filter={on ? "url(#glow)" : undefined} transform="translate(-2, 0)" />
        {[0, 1, 2].map((i) => (
          <path key={i} d={`M ${15 + i * 8} ${50 - i * 4} q ${8 + i * 2} 16 0 ${32 + i * 8}`} fill="none" stroke="#f0c05a" strokeWidth="2" strokeLinecap="round" opacity={on ? 1 - i * 0.25 : 0.08} />
        ))}
        <line x1="-10" y1="92" x2="-10" y2="112" stroke={item.color} strokeWidth="2.2" />
      </g>
    );
  }
  const on = item.brightness > 0;
  const duty = item.pin.type === "pwm_output" && on ? `  ${Math.round(item.brightness * 100)}%` : "";
  return (
    <g>
      <Caption item={item} state={`${on ? "ON" : "OFF"}${duty}  ${toggles}`} y={10} />
      <circle cy="62" r="46" fill="url(#ledGlow)" opacity={item.brightness} />
      <path d="M-14 78 v-20 a14 14 0 0 1 28 0 v20 Z" fill={on ? "#ffd98a" : "#3f4452"} stroke={on ? "#f0c05a" : "#59606f"} strokeWidth="1.5" />
      <rect x="-18" y="78" width="36" height="6" rx="1" fill={on ? "#f0c05a" : "#59606f"} />
      <line x1="0" y1="84" x2="0" y2="112" stroke={item.color} strokeWidth="2.2" />
    </g>
  );
}

function Gauge({ item }: { item: Live }) {
  const [lo, hi] = item.range;
  const frac = Math.max(0, Math.min(1, (item.value - lo) / (hi - lo || 1)));
  const angle = -120 + frac * 240;
  const R = 38;
  const point = (deg: number, r: number) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return `${(Math.cos(rad) * r).toFixed(2)} ${(Math.sin(rad) * r).toFixed(2)}`;
  };
  return (
    <g>
      <g transform="translate(0, 44)">
        <path d={`M ${point(-120, R)} A ${R} ${R} 0 1 1 ${point(120, R)}`} fill="none" stroke="#262b36" strokeWidth="6" strokeLinecap="round" />
        {frac > 0.002 && <path d={`M ${point(-120, R)} A ${R} ${R} 0 ${frac * 240 > 180 ? 1 : 0} 1 ${point(angle, R)}`} fill="none" stroke={item.floating ? "#e8a33d" : "#f0c05a"} strokeWidth="6" strokeLinecap="round" />}
        <line x1="0" y1="0" x2="0" y2={-R + 10} stroke="#e7e9ee" strokeWidth="2.2" strokeLinecap="round" transform={`rotate(${angle})`} />
        <circle r="4" fill="#e7e9ee" />
        <text x={-R - 6} y={R - 8} fontSize="10" textAnchor="end" fontFamily="IBM Plex Mono" fill="#7f8794">{lo}</text>
        <text x={R + 6} y={R - 8} fontSize="10" textAnchor="start" fontFamily="IBM Plex Mono" fill="#7f8794">{hi}</text>
      </g>
      <text y="84" textAnchor="middle" fontSize="17" fontWeight="500" fontFamily="IBM Plex Mono" fill="#e7e9ee">
        {item.value.toFixed(item.unit === "mV" ? 0 : 1)} {item.unit}
      </text>
      <text y="99" textAnchor="middle" fontSize="11" fontFamily="IBM Plex Sans" fontWeight="500" fill="#a2a9b6">
        {item.pin.pin} {shorten(item.pin.role)}{item.floating ? ", FLOATING" : `, ${Math.round(item.mv)} mV`}
      </text>
    </g>
  );
}
