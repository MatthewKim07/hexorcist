import { useEffect, useState } from "react";
import { api, RunSummary } from "../api";
import { duration } from "../format";
import { Verdict } from "./Common";

function when(seconds: number): string {
  return new Date(seconds * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function History() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.runs().then(setRuns).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <h1 className="headline mb-8">History</h1>
      {error && <p className="text-fail">Could not load runs: {error}</p>}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left">
          <thead className="label">
            <tr>
              <th className="pb-3 pr-4 font-normal">Name</th>
              <th className="pb-3 pr-4 font-normal">Verdict</th>
              <th className="pb-3 pr-4 text-right font-normal">Duration</th>
              <th className="pb-3 text-right font-normal">Date</th>
            </tr>
          </thead>
          <tbody>
            {runs?.map((run) => (
              <tr key={run.id} className="cursor-pointer border-t border-line transition-colors hover:bg-raised/60" onClick={() => (location.hash = `#/runs/${run.id}`)}>
                <td className="py-3.5 pr-4">
                  <a href={`#/runs/${run.id}`} onClick={(e) => e.stopPropagation()} className="hover:underline">
                    {run.title}
                  </a>
                </td>
                <td className="py-3.5 pr-4">
                  <Verdict status={run.status} />
                </td>
                <td className="num py-3.5 pr-4 text-right text-muted">{duration(run.created_at, run.finished_at) || "…"}</td>
                <td className="whitespace-nowrap py-3.5 text-right text-muted">{when(run.created_at)}</td>
              </tr>
            ))}
            {runs?.length === 0 && (
              <tr>
                <td colSpan={4} className="border-t border-line py-10 text-center text-faint">
                  No runs yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
