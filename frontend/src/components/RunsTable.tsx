import { KeyboardEvent } from "react";
import { Bug, CircleCheck, CircleHelp, CircleX, Loader2, LucideIcon, ShieldCheck, Wand2 } from "lucide-react";
import { RunSummary } from "../api";
import { displayTitle, shortDuration } from "../format";
import { iconProps } from "../icons";
import { Tone, TONE_TEXT } from "./Common";
import { Tooltip } from "./ui";

/** Table status labels: Fixed / Failed / Clean / Inconclusive / Running / Contained. */
function tableStatus(status: string): { label: string; tone: Tone; Icon: LucideIcon; spin?: boolean } {
  switch (status) {
    case "fixed":
      return { label: "Fixed", tone: "pass", Icon: CircleCheck };
    case "clean":
      return { label: "Clean", tone: "pass", Icon: CircleCheck };
    case "contained":
      return { label: "Contained", tone: "pass", Icon: ShieldCheck };
    case "running":
      return { label: "Running", tone: "neutral", Icon: Loader2, spin: true };
    case "inconclusive":
      return { label: "Inconclusive", tone: "neutral", Icon: CircleHelp };
    default:
      return { label: "Failed", tone: "fail", Icon: CircleX };
  }
}

function ago(seconds: number): string {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - seconds));
  if (s < 45) {
    return "just now";
  }
  if (s < 3600) {
    return `${Math.floor(s / 60)}m ago`;
  }
  if (s < 86400) {
    return `${Math.floor(s / 3600)}h ago`;
  }
  const d = Math.floor(s / 86400);
  return d === 1 ? "1d ago" : `${d}d ago`;
}

function StatusCell({ status }: { status: string }) {
  const meta = tableStatus(status);
  const color = status === "running" ? "text-running" : TONE_TEXT[meta.tone];
  return (
    <span className={`inline-flex items-center gap-2 ${color}`}>
      <meta.Icon {...iconProps} className={`shrink-0 ${meta.spin ? "animate-spin" : ""}`} />
      <span className="hidden sm:inline">{meta.label}</span>
    </span>
  );
}

function ModeCell({ mode, title, status }: { mode: string; title: string; status: string }) {
  const security = status === "contained" || status === "containment_failed" || /contain/i.test(title);
  const label = security ? "Security demo" : mode === "build" ? "Write firmware" : "Find bugs";
  const Icon = security ? ShieldCheck : mode === "build" ? Wand2 : Bug;
  return (
    <Tooltip content={label}>
      <span aria-label={label} className="inline-flex items-center justify-center text-muted">
        <Icon {...iconProps} />
      </span>
    </Tooltip>
  );
}

function openRun(id: string) {
  location.hash = `#/runs/${id}`;
}

function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, id: string) {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    openRun(id);
  }
}

/** Deployments-style runs table. Whole row links to the run. */
export function RunsTable({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="w-full">
      <table className="w-full table-fixed border-collapse text-left text-sm">
        <colgroup>
          <col className="w-7 sm:w-[130px]" />
          <col />
          <col className="hidden sm:table-column sm:w-12" />
          <col className="hidden sm:table-column sm:w-[90px]" />
          <col className="w-[90px]" />
        </colgroup>
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="pb-2 pr-2 font-normal sm:pr-4">Status</th>
            <th className="pb-2 pr-2 font-normal sm:pr-4">Name</th>
            <th className="hidden pb-2 pr-2 text-center font-normal sm:table-cell sm:pr-4">Mode</th>
            <th className="hidden pb-2 pr-2 font-normal sm:table-cell sm:pr-4">Duration</th>
            <th className="pb-2 text-right font-normal">Time</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              role="link"
              tabIndex={0}
              className="cursor-pointer border-b border-line transition-colors last:border-b-0 hover:bg-[#FAFAFA] focus-visible:bg-[#FAFAFA]"
              onClick={() => openRun(run.id)}
              onKeyDown={(e) => onRowKey(e, run.id)}
            >
              <td className="align-middle py-3 pr-2 sm:pr-4">
                <StatusCell status={run.status} />
              </td>
              <td className="align-middle py-3 pr-2 sm:pr-4">
                <span className="block truncate text-ink">{displayTitle(run.title)}</span>
              </td>
              <td className="hidden align-middle py-3 pr-2 text-center sm:table-cell sm:pr-4">
                <ModeCell mode={run.mode} title={run.title} status={run.status} />
              </td>
              <td className="num hidden align-middle py-3 pr-2 text-muted sm:table-cell sm:pr-4">{shortDuration(run.created_at, run.finished_at) || "—"}</td>
              <td className="align-middle whitespace-nowrap py-3 text-right text-muted">{ago(run.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
