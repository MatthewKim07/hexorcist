import { memo, useMemo, useRef, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, LineChart, ReferenceArea, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { PinSpec, Scenario, Trace, Violation } from "../api";
import { AnalogTrack, fmtTime, InputTrack, OutputTrack, parseScale, PIN_COLORS, toPhysical } from "../trace";

const AXIS_W = 52;
const RIGHT = 14;
const MAX_POINTS = 600;

interface LaneData {
  pin: PinSpec;
  color: string;
  kind: "analog" | "digital";
  unit: string;
  points: { t: number; v: number; band?: [number, number] }[];
}

function buildLanes(trace: Trace, pins: PinSpec[], scenario: Scenario | undefined, end: number): LaneData[] {
  return pins.map((pin, i) => {
    const color = PIN_COLORS[i % PIN_COLORS.length];
    if (pin.type === "analog_input") {
      const track = new AnalogTrack(trace, pin.pin);
      const scale = parseScale(pin.scale);
      const step = Math.max(1, Math.ceil(track.times.length / MAX_POINTS));
      const points: LaneData["points"] = [];
      for (let k = 0; k < track.times.length; k += step) {
        // Keep the extremes of each bucket, so a 5 ms spike survives decimation.
        const lows = track.low.slice(k, k + step);
        const highs = track.high.slice(k, k + step);
        points.push({
          t: track.times[k],
          v: toPhysical(track.mv[k], scale),
          band: [toPhysical(Math.min(...lows), scale), toPhysical(Math.max(...highs), scale)],
        });
      }
      return { pin, color, kind: "analog", unit: scale.unit, points };
    }
    let times: number[];
    let levels: number[];
    let initial = 0;
    if (pin.type === "digital_input") {
      initial = scenario?.digital?.find((d) => d.pin === pin.pin)?.initial ?? (pin.active_low ? 1 : 0);
      const track = new InputTrack(trace, pin.pin, initial);
      times = track.times;
      levels = track.levels;
    } else {
      const track = new OutputTrack(trace, pin.pin);
      times = track.times;
      levels = track.levels;
    }
    const points: LaneData["points"] = [{ t: 0, v: initial }];
    for (let k = 0; k < times.length; k++) {
      points.push({ t: times[k], v: levels[k] });
    }
    points.push({ t: end, v: levels.length ? levels[levels.length - 1] : initial });
    return { pin, color, kind: "digital", unit: "", points };
  });
}

const Lanes = memo(function Lanes({ lanes, violations, end }: { lanes: LaneData[]; violations: Violation[]; end: number }) {
  const minWidth = end * 0.004;
  const regions = violations.slice(0, 80).map((v, i) => (
    <ReferenceArea key={i} x1={v.t_start} x2={Math.max(v.t_end, v.t_start + minWidth)} fill="#f2555a" fillOpacity={0.2} stroke="none" ifOverflow="hidden" />
  ));
  const axisTick = { fill: "#7f8794", fontSize: 10, fontFamily: "IBM Plex Mono" };
  const xAxis = (show: boolean) => (
    <XAxis dataKey="t" type="number" domain={[0, end]} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}s`} tick={show ? axisTick : false} height={show ? 20 : 2} axisLine={{ stroke: "#262b36" }} tickLine={false} allowDataOverflow />
  );
  return (
    <>
      {lanes.map((lane, i) => {
        const last = i === lanes.length - 1;
        const label = (
          <div className="flex items-center gap-1.5 pl-[52px] text-[11px] text-muted">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: lane.color }} />
            <span className="font-mono text-ink">{lane.pin.pin}</span> {lane.pin.role}
            {lane.unit && lane.unit !== "mV" ? <span className="text-faint">({lane.unit})</span> : null}
          </div>
        );
        if (lane.kind === "analog") {
          return (
            <div key={lane.pin.pin}>
              {label}
              <ResponsiveContainer width="100%" height={last ? 138 : 118}>
                <ComposedChart data={lane.points} margin={{ top: 6, right: RIGHT, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="#1c2029" />
                  {xAxis(last)}
                  <YAxis width={AXIS_W} tick={axisTick} axisLine={false} tickLine={false} domain={["auto", "auto"]} tickCount={4} tickFormatter={(v: number) => `${Math.round(v * 10) / 10}`} />
                  {regions}
                  <Area dataKey="band" stroke="none" fill={lane.color} fillOpacity={0.22} isAnimationActive={false} />
                  <Line dataKey="v" stroke={lane.color} strokeWidth={2} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          );
        }
        return (
          <div key={lane.pin.pin}>
            {label}
            <ResponsiveContainer width="100%" height={last ? 66 : 46}>
              <LineChart data={lane.points} margin={{ top: 4, right: RIGHT, bottom: 0, left: 0 }}>
                {xAxis(last)}
                <YAxis width={AXIS_W} tick={axisTick} axisLine={false} tickLine={false} domain={[-0.1, 1.1]} ticks={[0, 1]} tickFormatter={(v: number) => (v ? "HIGH" : "LOW")} />
                {regions}
                <Line dataKey="v" type="stepAfter" stroke={lane.color} strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        );
      })}
    </>
  );
});

export function TraceChart({ trace, pins, scenario, violations, t, end, onScrub }: { trace: Trace; pins: PinSpec[]; scenario?: Scenario; violations: Violation[]; t: number; end: number; onScrub: (t: number) => void }) {
  const lanes = useMemo(() => buildLanes(trace, pins, scenario, end), [trace, pins, scenario, end]);
  const overlay = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ t: number; x: number; flip: boolean } | null>(null);

  const timeFromEvent = (clientX: number) => {
    const box = overlay.current!.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (clientX - box.left) / box.width));
    return { t: frac * end, x: frac * 100, flip: frac > 0.7 };
  };

  const valueAt = (lane: LaneData, at: number) => {
    let found = lane.points[0];
    for (const p of lane.points) {
      if (p.t > at) {
        break;
      }
      found = p;
    }
    if (!found) {
      return "";
    }
    return lane.kind === "analog" ? `${found.v.toFixed(1)} ${lane.unit}` : found.v ? "HIGH" : "LOW";
  };

  return (
    <div>
      <div className="relative space-y-1 select-none">
        <Lanes lanes={lanes} violations={violations} end={end} />
        <div
          ref={overlay}
          className="absolute bottom-0 top-0 cursor-crosshair"
          style={{ left: AXIS_W, right: RIGHT }}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            onScrub(timeFromEvent(e.clientX).t);
          }}
          onPointerMove={(e) => {
            const next = timeFromEvent(e.clientX);
            setHover(next);
            if (e.buttons) {
              onScrub(next.t);
            }
          }}
          onPointerLeave={() => setHover(null)}
        >
          <div className="pointer-events-none absolute bottom-5 top-0 w-px bg-accent" style={{ left: `${(t / end) * 100}%` }} />
          {hover && (
            <>
              <div className="pointer-events-none absolute bottom-5 top-0 w-px bg-faint/70" style={{ left: `${hover.x}%` }} />
              <div className="pointer-events-none absolute top-5 z-10 min-w-36 rounded-md border border-line bg-raised px-2.5 py-1.5 text-[11px] shadow-lg" style={hover.flip ? { right: `${100 - hover.x + 1}%` } : { left: `${hover.x + 1}%` }}>
                <div className="font-mono text-faint">{fmtTime(hover.t)}</div>
                {lanes.map((lane) => (
                  <div key={lane.pin.pin} className="flex items-center justify-between gap-3">
                    <span className="flex items-center gap-1.5 text-muted">
                      <span className="inline-block h-2 w-2 rounded-sm" style={{ background: lane.color }} />
                      {lane.pin.pin}
                    </span>
                    <span className="font-mono text-ink">{valueAt(lane, hover.t)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-4 pl-[52px] text-[11px] text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-4 rounded-sm bg-fail/40" />
          Check failed
        </span>
      </div>
    </div>
  );
}
