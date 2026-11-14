import { KeyboardEvent } from "react";
import { Bug, CircleCheck, CircleHelp, CircleX, Loader2, LucideIcon, ShieldCheck, Wand2 } from "lucide-react";
import { RunSummary } from "../api";
import { shortDuration } from "../format";
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

function ModeCell({ mode }: { mode: string }) {
  const build = mode === "build";
  const label = build ? "Write firmware" : "Find bugs";
  const Icon = build ? Wand2 : Bug;
  return (
    <Tooltip content={label}>
      <span aria-label={label} className="inline-flex text-muted">
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
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="pb-2 pr-3 font-normal sm:pr-4">Status</th>
            <th className="pb-2 pr-3 font-normal sm:pr-4">Name</th>
            <th className="hidden w-10 pb-2 pr-3 font-normal sm:table-cell sm:pr-4">Mode</th>
            <th className="hidden pb-2 pr-3 font-normal sm:table-cell sm:pr-4">Duration</th>
            <th className="pb-2 text-right font-normal sm:text-left">Time</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              role="link"
              tabIndex={0}
              className="cursor-pointer border-b border-line transition-colors last:border-b-0 hover:bg-[#FAFAFA] focus-visible:bg-[#FAFAFA] focus-visible:outline-none"
              onClick={() => openRun(run.id)}
              onKeyDown={(e) => onRowKey(e, run.id)}
            >
              <td className="py-3 pr-3 sm:pr-4">
                <StatusCell status={run.status} />
              </td>
              <td className="max-w-[1px] truncate py-3 pr-3 text-ink sm:pr-4">{run.title || "Untitled"}</td>
              <td className="hidden py-3 pr-3 sm:table-cell sm:pr-4">
                <ModeCell mode={run.mode} />
              </td>
              <td className="num hidden py-3 pr-3 text-muted sm:table-cell sm:pr-4">{shortDuration(run.created_at, run.finished_at) || "—"}</td>
              <td className="whitespace-nowrap py-3 text-right text-muted sm:text-left">{ago(run.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
