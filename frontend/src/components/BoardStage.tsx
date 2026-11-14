import { forwardRef, KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import * as RPopover from "@radix-ui/react-popover";
import { Check, PinSpec, Scenario, Trace } from "../api";
import { anchorOf, chipLabel, shortRole } from "../checks";
import { boardLayout, boardLive, HEADER_PINS, MCU_XY, partState, pinXY, USB_XY, VirtualBoard } from "./VirtualBoard";

export type ChipTone = "pass" | "fail" | "off" | "idle";

export interface StageChip {
  key: string;
  check: Check;
  tone: ChipTone;
  /** A brief red pulse, for the moment a check is being broken. */
  flash?: boolean;
  /** What the lamp means, for screen readers: "held", "broken in this scenario". */
  status?: string;
}

interface Props {
  pins: PinSpec[];
  trace: Trace | null;
  t: number;
  scenario?: Scenario;
  chips?: StageChip[];
  /** Setup: a chip opens an editor. */
  chipPopover?: (chip: StageChip, close: () => void) => ReactNode;
  /** Results: a chip jumps to its row. */
  onChip?: (chip: StageChip) => void;
  activeChip?: string | null;
  /** Setup: header pins open the wiring editor. */
  pinPopover?: (pin: string, close: () => void) => ReactNode;
  sketch?: { label: string; empty: boolean; onOpen: () => void };
  /** Show wiring and checks as plain lists under the board instead of on it. */
  list?: boolean;
  className?: string;
}

const NARROW = 640;
const MAX_STACK = 3;

function pct(v: number, from: number, span: number): string {
  return `${((v - from) / span) * 100}%`;
}

type ChipProps = { chip: StageChip; pins: PinSpec[]; active?: boolean; as?: "button" | "span" } & React.ButtonHTMLAttributes<HTMLButtonElement>;

export const RuleChip = forwardRef<HTMLButtonElement, ChipProps>(function RuleChip({ chip, pins, active = false, as = "button", ...rest }, ref) {
  const lamp = { pass: "bg-pass-lit", fail: "bg-fail-lit", off: "bg-screen-muted/50", idle: "border border-screen-muted bg-transparent" }[chip.tone];
  const label = chipLabel(chip.check, pins);
  const body = (
    <>
      <span aria-hidden="true" className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${lamp} ${chip.flash ? "chip-flash" : ""}`} />
      <span className="min-w-0 text-left leading-snug">{label}</span>
    </>
  );
  const look = `chip inline-flex max-w-full items-start gap-2 rounded-full border px-2.5 py-1 text-xs ${active ? "border-trace text-screen-ink" : "border-screen-line text-screen-ink"} bg-screen-raised`;
  if (as === "span") {
    return <span className={look}>{body}</span>;
  }
  return (
    <button ref={ref} type="button" aria-label={`${label}${chip.status ? `, ${chip.status}` : ""}`} aria-pressed={active || undefined} className={`key ${look} !font-normal hover:border-screen-muted`} {...rest}>
      {body}
    </button>
  );
});

function Pop({ open, onOpenChange, trigger, children, label }: { open: boolean; onOpenChange: (v: boolean) => void; trigger: ReactNode; children: ReactNode; label: string }) {
  return (
    <RPopover.Root open={open} onOpenChange={onOpenChange}>
      <RPopover.Trigger asChild>{trigger}</RPopover.Trigger>
      <RPopover.Portal>
        <RPopover.Content aria-label={label} side="bottom" align="center" sideOffset={8} collisionPadding={12} className="pop z-50 w-[300px] rounded-lg border border-line bg-raised p-4 text-sm text-ink shadow-[0_8px_24px_rgba(18,24,22,0.12)]">
          {children}
        </RPopover.Content>
      </RPopover.Portal>
    </RPopover.Root>
  );
}

/** The board with what sits on it: wiring hotspots on the header, rule chips beside their parts, and the sketch on the chip. */
export function BoardStage({ pins, trace, t, scenario, chips = [], chipPopover, onChip, activeChip = null, pinPopover, sketch, list = false, className = "" }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [narrow, setNarrow] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [focusPin, setFocusPin] = useState(0);
  const pinRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!box.current) {
      return;
    }
    const ro = new ResizeObserver(([entry]) => setNarrow(entry.contentRect.width < NARROW));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  const used = new Map(pins.map((p) => [p.pin, p]));
  const probe = boardLayout(pins, chips.length > 0 || !!pinPopover);
  const groups = new Map<string, StageChip[]>();
  for (const chip of chips) {
    const at = anchorOf(chip.check);
    const key = at === "usb" || !probe.slots.some((s) => s.pin === at) ? "usb" : at;
    groups.set(key, [...(groups.get(key) ?? []), chip]);
  }
  const topCount = probe.slots.filter((s) => s.top).length;
  const crowded = topCount > 3 || [...groups.values()].some((g) => g.length > MAX_STACK);
  const asList = list || narrow || crowded;
  // Side overlays need the wide viewBox; the list mode crops to the board so it fills the panel.
  const overlays = (!asList && chips.length > 0) || !!pinPopover;
  const layout = boardLayout(pins, overlays);
  const { view } = layout;
  const live = useMemo(() => boardLive(pins, trace, t, scenario), [pins, trace, t, scenario]);

  const chipButton = (chip: StageChip) => {
    const id = `chip:${chip.key}`;
    if (chipPopover) {
      return (
        <Pop key={chip.key} label={chipLabel(chip.check, pins)} open={open === id} onOpenChange={(v) => setOpen(v ? id : null)} trigger={<RuleChip chip={chip} pins={pins} active={open === id} />}>
          {chipPopover(chip, () => setOpen(null))}
        </Pop>
      );
    }
    if (onChip) {
      return <RuleChip key={chip.key} chip={chip} pins={pins} active={activeChip === chip.key} onClick={() => onChip(chip)} />;
    }
    return <RuleChip key={chip.key} chip={chip} pins={pins} as="span" />;
  };

  const pinButton = (pin: string, i: number, extra: string, text?: ReactNode) => {
    const id = `pin:${pin}`;
    const p = used.get(pin);
    const label = p ? `${pin}, ${shortRole(p, "unnamed")}, ${p.type.replace("_", " ")}` : `${pin}, not wired`;
    return (
      <Pop
        key={pin}
        label={`Wiring for ${pin}`}
        open={open === id}
        onOpenChange={(v) => setOpen(v ? id : null)}
        trigger={
          <button
            type="button"
            ref={(el) => (pinRefs.current[i] = el)}
            aria-label={label}
            tabIndex={i === focusPin ? 0 : -1}
            onFocus={() => setFocusPin(i)}
            onKeyDown={(e: KeyboardEvent) => {
              const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
              if (step) {
                e.preventDefault();
                const next = (i + step + HEADER_PINS.length) % HEADER_PINS.length;
                setFocusPin(next);
                pinRefs.current[next]?.focus();
              }
            }}
            className={extra}
          >
            {text}
          </button>
        }
      >
        {pinPopover?.(pin, () => setOpen(null))}
      </Pop>
    );
  };

  const groupStyle = (key: string): React.CSSProperties => {
    if (key === "usb") {
      return { left: pct(USB_XY.x - 16, view.x, view.w), top: pct(USB_XY.y, 0, view.h), transform: "translate(-100%, -50%)", alignItems: "flex-end" };
    }
    const slot = layout.slots.find((s) => s.pin === key)!;
    const right = topCount <= 1 || slot.x >= 480 || !slot.top;
    const y = slot.top ? 64 : slot.y + 46;
    // A gauge's scale labels reach further out than a fan's blades.
    const reach = slot.top ? 54 : 72;
    return right
      ? { left: pct(slot.x + reach, view.x, view.w), top: pct(y, 0, view.h), transform: "translate(0, -50%)", alignItems: "flex-start" }
      : { left: pct(slot.x - 54, view.x, view.w), top: pct(y, 0, view.h), transform: "translate(-100%, -50%)", alignItems: "flex-end" };
  };

  return (
    <div className={className}>
      <div ref={box} className="relative w-full overflow-hidden" style={{ aspectRatio: `${view.w} / ${view.h}` }}>
        <VirtualBoard pins={pins} trace={trace} t={t} scenario={scenario} full={overlays} captions={!asList} className="absolute inset-0 block h-full w-full" />

        {sketch && !asList && (
          <button
            type="button"
            onClick={sketch.onOpen}
            className={`key absolute flex -translate-x-1/2 -translate-y-1/2 flex-col rounded-[4px] px-3 py-1 text-center text-[11px] !font-normal leading-4 ${sketch.empty ? "border border-dashed border-trace bg-screen/90 text-trace" : "border border-transparent bg-[#15171c] text-screen-ink hover:border-screen-muted"}`}
            style={{ left: pct(MCU_XY.x, view.x, view.w), top: pct(MCU_XY.y, 0, view.h), width: pct(view.x + 184, view.x, view.w) }}
          >
            <span className="truncate font-mono">{sketch.label}</span>
            <span className="text-screen-muted">{sketch.empty ? "Paste your sketch" : "Edit the sketch"}</span>
          </button>
        )}

        {pinPopover && !asList && (
          <div role="group" aria-label="Header pins. Arrow keys move between pins, Enter opens the wiring for one.">
            {HEADER_PINS.map((pin, i) => {
              const { x, y } = pinXY(pin);
              const size = pct(view.x + 20, view.x, view.w);
              return (
                <span key={pin} className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: pct(x, view.x, view.w), top: pct(y, 0, view.h), width: size, aspectRatio: "1" }}>
                  {pinButton(pin, i, "pin-hot block h-full w-full rounded-[3px]")}
                </span>
              );
            })}
          </div>
        )}

        {!asList &&
          [...groups.entries()].map(([key, group]) => (
            <div key={key} role="group" aria-label={key === "usb" ? "Serial and timing checks" : `Checks on ${key} ${shortRole(used.get(key))}`} className="absolute flex flex-col gap-1.5" style={groupStyle(key)}>
              {group.map(chipButton)}
            </div>
          ))}
      </div>

      {asList && (pinPopover || chips.length > 0 || sketch || live.length > 0) && (
        <div className="space-y-3 px-3 pb-3 pt-2 text-sm text-screen-ink sm:px-4">
          {sketch && (
            <button type="button" onClick={sketch.onOpen} className={`key flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-xs !font-normal ${sketch.empty ? "border-dashed border-trace text-trace" : "border-screen-line text-screen-ink hover:border-screen-muted"}`}>
              <span className="truncate font-mono">{sketch.label}</span>
              <span className="shrink-0 text-screen-muted">{sketch.empty ? "Paste your sketch" : "Edit the sketch"}</span>
            </button>
          )}
          {pinPopover && (
            <div role="group" aria-label="Header pins. Arrow keys move between pins, Enter opens the wiring for one.">
              <p className="mb-2 text-xs text-screen-muted">Wiring</p>
              <div className="flex flex-wrap gap-1.5">
                {HEADER_PINS.map((pin, i) => {
                  const p = used.get(pin);
                  return pinButton(
                    pin,
                    i,
                    `key rounded-full border px-2.5 py-1 text-xs !font-normal ${p ? "border-screen-muted bg-screen-raised text-screen-ink" : "border-screen-line text-screen-muted hover:text-screen-ink"}`,
                    <>
                      <span className="font-mono">{pin}</span>
                      {p && <span>{shortRole(p, "unnamed")}</span>}
                    </>,
                  );
                })}
              </div>
            </div>
          )}
          {live.length > 0 && (
            <ul className="space-y-2.5" aria-label="Parts and checks">
              {layout.slots.map((slot) => {
                const item = live.find((l) => l.pin.pin === slot.pin);
                if (!item) {
                  return null;
                }
                const group = groups.get(slot.pin) ?? [];
                return (
                  <li key={slot.pin} className="space-y-1.5">
                    <div className="flex min-w-0 items-baseline justify-between gap-3">
                      <span className="min-w-0 truncate text-xs text-screen-ink">
                        <span className="font-mono">{item.pin.pin}</span> {shortRole(item.pin)}
                      </span>
                      <span className="shrink-0 font-mono text-[11px] text-screen-muted">{partState(item)}</span>
                    </div>
                    {group.length > 0 && <div className="flex flex-wrap gap-1.5">{group.map(chipButton)}</div>}
                  </li>
                );
              })}
              {(groups.get("usb") ?? []).length > 0 && (
                <li className="space-y-1.5">
                  <p className="text-xs text-screen-muted">Serial, timing</p>
                  <div className="flex flex-wrap gap-1.5">{(groups.get("usb") ?? []).map(chipButton)}</div>
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
