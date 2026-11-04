import { ReactNode } from "react";

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <ellipse cx="16" cy="6.5" rx="8" ry="2.6" fill="none" stroke="#f0c05a" strokeWidth="2" style={{ filter: "drop-shadow(0 0 3px rgba(240,192,90,0.8))" }} />
      <rect x="9" y="13" width="14" height="14" rx="2" fill="#181c25" stroke="#e7e9ee" strokeWidth="1.6" />
      <path d="M13 13v-2M19 13v-2M13 29v-2M19 29v-2M9 18H7M9 23H7M25 18h-2M25 23h-2" stroke="#e7e9ee" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M13.5 20l2 2 3.5-4" fill="none" stroke="#f0c05a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type IconName = "check" | "x" | "dash" | "dot" | "warn" | "shield" | "play" | "pause" | "restart";

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
  };
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

const TONES = {
  pass: "border-pass/40 bg-pass/10 text-pass",
  fail: "border-fail/40 bg-fail/10 text-fail",
  warn: "border-warn/40 bg-warn/10 text-warn",
  halo: "border-halo/40 bg-halo/10 text-halo",
  neutral: "border-line bg-raised text-muted",
};

export function Badge({ tone = "neutral", icon, children, title }: { tone?: keyof typeof TONES; icon?: IconName; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] leading-4 ${TONES[tone]}`}>
      {icon && <Icon name={icon} className="h-3 w-3" />}
      {children}
    </span>
  );
}

export function Panel({ title, right, children, className = "" }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <h2 className="panel-title">{title}</h2>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function DiffView({ unified }: { unified: string }) {
  const lines = unified.split("\n").filter((l) => !l.startsWith("---") && !l.startsWith("+++"));
  return (
    <pre className="max-h-96 overflow-auto rounded-md border border-line bg-bg py-2 font-mono text-[12px] leading-5">
      {lines.map((line, i) => {
        const add = line.startsWith("+");
        const del = line.startsWith("-");
        const hunk = line.startsWith("@@");
        return (
          <div key={i} className={`whitespace-pre px-3 ${add ? "bg-pass/10 text-pass" : del ? "bg-fail/10 text-fail" : hunk ? "text-faint" : "text-muted"}`}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

export const STATUS_META: Record<string, { label: string; tone: keyof typeof TONES; icon: IconName }> = {
  running: { label: "Running", tone: "halo", icon: "dot" },
  fixed: { label: "Fixed and verified", tone: "pass", icon: "check" },
  clean: { label: "Clean", tone: "pass", icon: "check" },
  partial: { label: "Partly fixed", tone: "warn", icon: "warn" },
  unfixed: { label: "Bugs found, no working fix", tone: "fail", icon: "x" },
  inconclusive: { label: "Inconclusive", tone: "warn", icon: "warn" },
  compile_failed: { label: "Does not compile", tone: "fail", icon: "x" },
  contained: { label: "Contained", tone: "pass", icon: "shield" },
  containment_failed: { label: "Containment check failed", tone: "fail", icon: "x" },
  blocked: { label: "Blocked by guard", tone: "warn", icon: "shield" },
  interrupted: { label: "Interrupted", tone: "warn", icon: "warn" },
  error: { label: "Error", tone: "fail", icon: "x" },
};

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "neutral" as const, icon: "dot" as const };
  return (
    <Badge tone={meta.tone} icon={meta.icon}>
      {meta.label}
    </Badge>
  );
}
