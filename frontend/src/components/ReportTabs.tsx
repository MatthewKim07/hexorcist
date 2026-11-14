import { KeyboardEvent, ReactNode, useId } from "react";
import { FlaskConical, ListChecks, LucideIcon, Scale, ScrollText, Shield } from "lucide-react";
import { iconProps } from "../icons";

export type ReportTabId = "scenarios" | "checks" | "containment" | "compare" | "logs";

const META: Record<ReportTabId, { label: string; Icon: LucideIcon }> = {
  scenarios: { label: "Scenarios", Icon: FlaskConical },
  checks: { label: "Checks", Icon: ListChecks },
  containment: { label: "Containment", Icon: Shield },
  compare: { label: "Compare", Icon: Scale },
  logs: { label: "Logs", Icon: ScrollText },
};

/** Vercel-style underline tabs with icons and arrow-key navigation. */
export function ReportTabs({ tabs, value, onChange, children }: { tabs: ReportTabId[]; value: ReportTabId | null; onChange: (id: ReportTabId | null) => void; children: ReactNode }) {
  const baseId = useId().replace(/:/g, "");
  if (!tabs.length) {
    return null;
  }
  const active = value && tabs.includes(value) ? value : tabs[0];

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = tabs.indexOf(active);
    if (i < 0) {
      return;
    }
    let next = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      next = (i + 1) % tabs.length;
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      next = (i - 1 + tabs.length) % tabs.length;
    } else if (e.key === "Home") {
      next = 0;
    } else if (e.key === "End") {
      next = tabs.length - 1;
    } else {
      return;
    }
    e.preventDefault();
    onChange(tabs[next]);
    document.getElementById(`${baseId}-tab-${tabs[next]}`)?.focus();
  };

  return (
    <section aria-label="Details">
      <div className="flex gap-5 overflow-x-auto border-b border-line" role="tablist" aria-orientation="horizontal" onKeyDown={onKeyDown}>
        {tabs.map((id) => {
          const meta = META[id];
          const selected = active === id;
          return (
            <button
              key={id}
              id={`${baseId}-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`${baseId}-panel`}
              tabIndex={selected ? 0 : -1}
              className={`inline-flex shrink-0 items-center gap-1.5 border-b-2 pb-2.5 text-sm transition-colors ${selected ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"}`}
              onClick={() => onChange(id)}
            >
              <meta.Icon {...iconProps} aria-hidden="true" />
              {meta.label}
            </button>
          );
        })}
      </div>
      <div id={`${baseId}-panel`} role="tabpanel" aria-labelledby={`${baseId}-tab-${active}`}>
        {children}
      </div>
    </section>
  );
}
