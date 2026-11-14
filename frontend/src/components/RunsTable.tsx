import { KeyboardEvent } from "react";
import { RunSummary } from "../api";
import { duration } from "../format";
import { Tone, TONE_TEXT } from "./Common";

/** Table status labels: Fixed / Failed / Clean / Inconclusive / Running / Contained. */
function tableStatus(status: string): { label: string; tone: Tone } {
  switch (status) {
    case "fixed":
      return { label: "Fixed", tone: "pass" };
    case "clean":
      return { label: "Clean", tone: "pass" };
    case "contained":
      return { label: "Contained", tone: "pass" };
    case "running":
      return { label: "Running", tone: "neutral" };
    case "inconclusive":
      return { label: "Inconclusive", tone: "neutral" };
    default:
      return { label: "Failed", tone: "fail" };
  }
}

function modeLabel(mode: string): string {
  return mode === "build" ? "Write firmware" : "Find bugs";
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
  const dot = status === "running" ? "bg-running" : meta.tone === "pass" ? "bg-pass" : meta.tone === "fail" ? "bg-fail" : "bg-queued";
  return (
    <span className={`inline-flex items-center gap-2 ${status === "running" ? "text-running" : TONE_TEXT[meta.tone]}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      {meta.label}
    </span>
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
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th className="pb-2 pr-4 font-normal">Status</th>
            <th className="pb-2 pr-4 font-normal">Name</th>
            <th className="pb-2 pr-4 font-normal">Mode</th>
            <th className="pb-2 pr-4 font-normal">Duration</th>
            <th className="pb-2 font-normal">Time</th>
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
              <td className="py-3 pr-4">
                <StatusCell status={run.status} />
              </td>
              <td className="max-w-[240px] truncate py-3 pr-4 text-ink">{run.title || "Untitled"}</td>
              <td className="py-3 pr-4 text-muted">{modeLabel(run.mode)}</td>
              <td className="num py-3 pr-4 text-muted">{duration(run.created_at, run.finished_at) || "—"}</td>
              <td className="py-3 text-muted">{ago(run.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
