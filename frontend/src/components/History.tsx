import { useEffect, useState } from "react";
import { api, RunSummary } from "../api";
import { duration } from "../format";
import { Verdict } from "./Common";

function when(seconds: number): string {
  return new Date(seconds * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

/** Every run, newest first, one row each. */
export function History({ onOpen }: { onOpen?: () => void }) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.runs().then(setRuns).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="py-2">
      {error && <p className="py-4 text-fail">Could not load runs: {error}</p>}
      {runs === null && !error && <p className="py-4 text-muted">Loading</p>}
      {runs?.length === 0 && <p className="py-10 text-center text-muted">No runs yet. Load an example and run it.</p>}
      <ul>
        {runs?.map((run) => (
          <li key={run.id} className="border-b border-line last:border-b-0">
            <a href={`#/runs/${run.id}`} onClick={onOpen} className="hover-row -mx-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-0.5 rounded px-2 py-3 transition-colors">
              <span className="truncate">{run.title}</span>
              <span className="text-right text-sm">
                <Verdict status={run.status} />
              </span>
              <span className="text-xs text-muted">{when(run.created_at)}</span>
              <span className="num text-right text-xs text-muted">{duration(run.created_at, run.finished_at) || "Running"}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
