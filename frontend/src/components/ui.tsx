import { ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import * as RCheckbox from "@radix-ui/react-checkbox";
import * as RCollapsible from "@radix-ui/react-collapsible";
import * as RSelect from "@radix-ui/react-select";
import * as RToggle from "@radix-ui/react-toggle-group";
import * as RTooltip from "@radix-ui/react-tooltip";
import { Icon } from "./Common";

export function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Places an indicator under (or behind) the selected item, and moves it when the selection moves. */
function useIndicator(selector: string, deps: unknown[]) {
  const box = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0, w: 0, h: 0, ready: false, animate: false });
  const place = useCallback(
    (animate: boolean) => {
      const el = box.current?.querySelector<HTMLElement>(selector);
      if (!el) {
        setPos((p) => ({ ...p, ready: false }));
        return;
      }
      const scroll = el.parentElement?.scrollLeft ?? 0;
      setPos((p) => ({ x: el.offsetLeft - scroll, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight, ready: true, animate: animate && p.ready }));
    },
    [selector],
  );
  useLayoutEffect(() => place(true), [place, ...deps]);
  useEffect(() => {
    if (!box.current) {
      return;
    }
    // Resizes and late font loads move the item without the user asking, so the indicator follows without animating.
    const still = () => place(false);
    const ro = new ResizeObserver(still);
    ro.observe(box.current);
    document.fonts?.ready.then(still);
    return () => ro.disconnect();
  }, [place]);
  return { box, pos, replace: () => place(false) };
}

/* ------------------------------------------------------------------ Select */

export interface Option<T extends string> {
  value: T;
  label: ReactNode;
}

export function Select<T extends string>({ value, onChange, options, label, mono = false, className = "" }: { value: T; onChange: (v: T) => void; options: Option<T>[]; label: string; mono?: boolean; className?: string }) {
  return (
    <RSelect.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <RSelect.Trigger aria-label={label} className={`key flex h-9 min-w-0 items-center justify-between gap-2 rounded-md border border-line bg-white px-3 !py-0 text-sm !font-normal text-ink ${mono ? "font-mono" : ""} ${className}`}>
        <span className="min-w-0 truncate text-left">
          <RSelect.Value />
        </span>
        <RSelect.Icon className="shrink-0 text-muted">
          <Icon name="chevronDown" className="h-3 w-3" />
        </RSelect.Icon>
      </RSelect.Trigger>
      <RSelect.Portal>
        <RSelect.Content position="popper" sideOffset={6} className="pop z-50 max-h-[min(360px,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-line bg-white p-1 text-sm text-ink">
          <RSelect.Viewport className="scroll">
            {options.map((o) => (
              <RSelect.Item key={o.value} value={o.value} className={`relative flex cursor-default select-none items-center rounded py-1.5 pl-7 pr-3 outline-none data-[highlighted]:bg-bg ${mono ? "font-mono" : ""}`}>
                <RSelect.ItemIndicator className="absolute left-2 text-ink">
                  <Icon name="check" className="h-3 w-3" />
                </RSelect.ItemIndicator>
                <RSelect.ItemText>{typeof o.label === "string" ? o.label : String(o.value)}</RSelect.ItemText>
              </RSelect.Item>
            ))}
          </RSelect.Viewport>
        </RSelect.Content>
      </RSelect.Portal>
    </RSelect.Root>
  );
}

/* ---------------------------------------------------------------- Checkbox */

export function Checkbox({ checked, onChange, children, className = "", hint }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode; className?: string; hint?: string }) {
  // A tooltip trigger takes over data-state, so the checked look keys off aria-checked.
  const box = (
    <RCheckbox.Root checked={checked} onCheckedChange={(v) => onChange(v === true)} className="key h-4 w-4 shrink-0 rounded-[4px] border border-line bg-white aria-checked:border-ink aria-checked:bg-ink">
      <RCheckbox.Indicator className="text-white">
        <Icon name="check" className="h-3 w-3" />
      </RCheckbox.Indicator>
    </RCheckbox.Root>
  );
  return (
    <label className={`group flex cursor-pointer select-none items-center gap-2 ${className}`}>
      {hint ? <Tip content={hint}>{box}</Tip> : box}
      {children}
    </label>
  );
}

/* --------------------------------------------------------------- Segmented */

/** Two or three exclusive options, with a block that slides to the chosen one. */
export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: Option<T>[]; label: string }) {
  const { box, pos } = useIndicator('[aria-checked="true"]', [value]);
  return (
    <RToggle.Root type="single" value={value} onValueChange={(v) => v && onChange(v as T)} aria-label={label} asChild>
      <div ref={box} className="relative flex rounded-md border border-line bg-white p-0.5">
        <span
          aria-hidden="true"
          className={`absolute bottom-0.5 left-0 top-0.5 rounded-[5px] bg-ink ${pos.animate ? "indicator" : ""}`}
          style={{ transform: `translateX(${pos.x}px)`, width: pos.w, opacity: pos.ready ? 1 : 0 }}
        />
        {options.map((o) => (
          <RToggle.Item key={o.value} value={o.value} className="key relative z-10 inline-flex items-center gap-1.5 rounded-[5px] px-4 py-1.5 !font-normal text-muted aria-checked:text-white">
            {o.label}
          </RToggle.Item>
        ))}
      </div>
    </RToggle.Root>
  );
}

/* ----------------------------------------------------------------- Tooltip */

export function TipProvider({ children }: { children: ReactNode }) {
  return (
    <RTooltip.Provider delayDuration={150} skipDelayDuration={300}>
      {children}
    </RTooltip.Provider>
  );
}

/** Dark accessible tooltip. Prefer this for new UI; Tip is the same. */
export function Tooltip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <RTooltip.Root delayDuration={150}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content side={side} sideOffset={6} collisionPadding={12} className="pop z-50 max-w-[280px] rounded-md bg-ink px-2.5 py-1.5 text-[12px] leading-snug text-white">
          {content}
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  );
}

export function Tip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "bottom" }) {
  return (
    <Tooltip content={content} side={side}>
      {children}
    </Tooltip>
  );
}

/* -------------------------------------------------------------------- Fold */

/** A disclosure that opens by height. */
export function Fold({ title, children, defaultOpen = false, className = "", contentClassName = "" }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string; contentClassName?: string }) {
  return (
    <RCollapsible.Root defaultOpen={defaultOpen} className={className}>
      <RCollapsible.Trigger className="hover-ink flex items-center gap-2 text-sm text-muted transition-colors data-[state=open]:text-ink">
        <Icon name="chevron" className="chev h-3 w-3" />
        {title}
      </RCollapsible.Trigger>
      <RCollapsible.Content className="fold">
        <div className={`pt-3 ${contentClassName}`}>{children}</div>
      </RCollapsible.Content>
    </RCollapsible.Root>
  );
}

export const Collapsible = RCollapsible;

/* ----------------------------------------------------------------- Counter */

/** Counts from zero to `value` when it first appears or changes. */
export function useTicker(value: number, ms = 450): number {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0));
  useEffect(() => {
    if (reducedMotion() || !Number.isFinite(value) || value === 0) {
      setShown(value);
      return;
    }
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / ms);
      setShown(Math.round(value * (1 - Math.pow(1 - k, 3))));
      if (k < 1) {
        frame = requestAnimationFrame(step);
      }
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, ms]);
  return shown;
}

/** Text whose first standalone whole number ticks up: the 23 in "D9 switched 23× in 5 s". Screen readers get the final text. */
export function Ticking({ text, className = "" }: { text: string; className?: string }) {
  const match = /(?<![A-Za-z\d.])\d+(?![.,\d])/.exec(text);
  const target = match ? Number(match[0]) : NaN;
  const n = useTicker(target);
  if (!match) {
    return <span className={className}>{text}</span>;
  }
  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
        {text.slice(0, match.index)}
        <span className="inline-block text-right tabular-nums" style={{ minWidth: `${match[0].length}ch` }}>
          {n}
        </span>
        {text.slice(match.index + match[0].length)}
      </span>
    </span>
  );
}

/* ---------------------------------------------------------------- Scrubber */

interface ScrubberProps {
  value: number;
  max: number;
  onChange: (v: number) => void;
  onScrubStart?: () => void;
  onScrubEnd?: () => void;
  label: string;
  valueText: string;
  disabled?: boolean;
}

/** The replay scrubber. Arrows move 100 ms (Shift 1 s), Page keys 1 s, Home and End jump to the ends. */
export function Scrubber({ value, max, onChange, onScrubStart, onScrubEnd, label, valueText, disabled }: ScrubberProps) {
  const track = useRef<HTMLDivElement>(null);
  const pending = useRef<number | null>(null);
  const frame = useRef(0);
  const [dragging, setDragging] = useState(false);
  const frac = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;

  const fromPointer = (clientX: number) => {
    const box = track.current!.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - box.left) / box.width)) * max;
  };
  const push = (v: number) => {
    pending.current = v;
    if (!frame.current) {
      frame.current = requestAnimationFrame(() => {
        frame.current = 0;
        if (pending.current !== null) {
          onChange(pending.current);
          pending.current = null;
        }
      });
    }
  };
  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const step = (e: React.KeyboardEvent) => {
    const small = e.shiftKey ? 1000 : 100;
    const keys: Record<string, number> = { ArrowRight: value + small, ArrowUp: value + small, ArrowLeft: value - small, ArrowDown: value - small, PageUp: value + 1000, PageDown: value - 1000, Home: 0, End: max };
    if (e.key in keys) {
      e.preventDefault();
      onChange(Math.max(0, Math.min(max, keys[e.key])));
    }
  };

  return (
    <div
      ref={track}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={Math.round(max)}
      aria-valuenow={Math.round(value)}
      aria-valuetext={valueText}
      aria-disabled={disabled || undefined}
      data-dragging={dragging || undefined}
      className={`group relative h-6 min-w-0 flex-1 touch-none select-none rounded outline-none focus-visible:outline-none ${disabled ? "opacity-40" : "cursor-pointer"}`}
      onKeyDown={disabled ? undefined : step}
      onPointerDown={(e) => {
        if (disabled || e.button !== 0) {
          return;
        }
        e.currentTarget.setPointerCapture(e.pointerId);
        e.currentTarget.focus();
        setDragging(true);
        onScrubStart?.();
        onChange(fromPointer(e.clientX));
      }}
      onPointerMove={(e) => {
        if (dragging) {
          push(fromPointer(e.clientX));
        }
      }}
      onPointerUp={(e) => {
        if (!dragging) {
          return;
        }
        e.currentTarget.releasePointerCapture(e.pointerId);
        setDragging(false);
        onChange(fromPointer(e.clientX));
        onScrubEnd?.();
      }}
      onPointerCancel={() => {
        setDragging(false);
        onScrubEnd?.();
      }}
    >
      <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 overflow-hidden rounded-full bg-screen-line">
        <div className="h-full w-full origin-left rounded-full bg-trace" style={{ transform: `scaleX(${frac})` }} />
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-0 right-0" style={{ transform: `translateX(${frac * 100}%)` }}>
        <div className="absolute left-0 top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-trace ring-4 ring-screen transition-transform duration-150 ease-out group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-offset-[5px] group-focus-visible:outline-[#7cc4dc] group-data-[dragging]:scale-125" />
      </div>
    </div>
  );
}
