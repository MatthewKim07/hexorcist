import { ReactNode } from "react";
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

/** Vercel-style underline tabs with icons. */
export function ReportTabs({ tabs, value, onChange, children }: { tabs: ReportTabId[]; value: ReportTabId | null; onChange: (id: ReportTabId | null) => void; children: ReactNode }) {
  if (!tabs.length) {
    return null;
  }
  const active = value && tabs.includes(value) ? value : tabs[0];
  return (
    <section aria-label="Details">
      <div className="flex gap-5 overflow-x-auto border-b border-line" role="tablist">
        {tabs.map((id) => {
          const meta = META[id];
          const selected = active === id;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={selected}
              className={`inline-flex shrink-0 items-center gap-1.5 border-b-2 pb-2.5 text-sm transition-colors ${selected ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"}`}
              onClick={() => onChange(id)}
            >
              <meta.Icon {...iconProps} />
              {meta.label}
            </button>
          );
        })}
      </div>
      <div role="tabpanel">{children}</div>
    </section>
  );
}
