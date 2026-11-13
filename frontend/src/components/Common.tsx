import { ReactNode } from "react";

export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="9" y="9" width="14" height="14" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M13 9V6M19 9V6M13 26v-3M19 26v-3M9 13H6M9 19H6M26 13h-3M26 19h-3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M13.5 16.5l2 2 3.5-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type IconName = "check" | "x" | "dash" | "dot" | "warn" | "shield" | "play" | "pause" | "restart" | "chevron" | "chevronDown" | "arrow";

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    check: <path d="M3.5 8.5l3 3 6-7" />,
    x: <path d="M4 4l8 8M12 4l-8 8" />,
    dash: <path d="M4 8h8" />,
    dot: <circle cx="8" cy="8" r="2.5" fill="currentColor" stroke="none" />,
    warn: <path d="M8 2.5l6 10.5H2L8 2.5zM8 6.5v3M8 11.3v.2" />,
    shield: <path d="M8 2l5 2v4c0 3-2.2 5-5 6-2.8-1-5-3-5-6V4l5-2z" />,
    play: <path d="M5 3l8 5-8 5V3z" fill="currentColor" />,
    pause: <path d="M5 3v10M11 3v10" />,
    restart: <path d="M3.5 8a4.5 4.5 0 1 0 1.4-3.3M3.5 2.5v3h3" />,
    chevron: <path d="M6 3.5L10.5 8 6 12.5" />,
    chevronDown: <path d="M3.5 6L8 10.5 12.5 6" />,
    arrow: <path d="M2.5 8h11M9.5 4l4 4-4 4" />,
  };
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

export function DiffView({ unified }: { unified: string }) {
  const lines = unified.split("\n").filter((l) => !l.startsWith("---") && !l.startsWith("+++"));
  return (
    <pre className="scroll max-h-96 overflow-auto rounded-md border border-line bg-raised py-2 font-mono text-xs leading-5">
      {lines.map((line, i) => {
        const add = line.startsWith("+");
        const del = line.startsWith("-");
        return (
          <div key={i} className={`whitespace-pre px-3 ${add ? "bg-pass/10 text-pass" : del ? "bg-fail/10 text-fail" : "text-muted"}`}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

export type Tone = "pass" | "fail" | "neutral";

export const STATUS_META: Record<string, { label: string; tone: Tone }> = {
  running: { label: "Running", tone: "neutral" },
  fixed: { label: "Fixed", tone: "pass" },
  clean: { label: "Clean", tone: "pass" },
  partial: { label: "Partly fixed", tone: "fail" },
  unfixed: { label: "Not fixed", tone: "fail" },
  inconclusive: { label: "Inconclusive", tone: "neutral" },
  compile_failed: { label: "Does not compile", tone: "fail" },
  contained: { label: "Contained", tone: "pass" },
  containment_failed: { label: "Not contained", tone: "fail" },
  blocked: { label: "Blocked", tone: "neutral" },
  interrupted: { label: "Interrupted", tone: "neutral" },
  error: { label: "Error", tone: "fail" },
};

export const TONE_TEXT: Record<Tone, string> = { pass: "text-pass", fail: "text-fail", neutral: "text-muted" };

/** A status as a coloured dot and one word. No badge box. */
export function Verdict({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "neutral" as Tone };
  return (
    <span className={`inline-flex items-center gap-1.5 ${TONE_TEXT[meta.tone]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {meta.label}
    </span>
  );
}
