import { useEffect, useState } from "react";
import { api, RunSummary } from "../api";
import { RunsTable } from "./RunsTable";

/** Full runs list, same data the old History drawer used. */
export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .runs()
      .then(setRuns)
      .catch((e) => setError((e as Error).message));
  }, []);

  return (
    <div>
      <h1 className="text-[32px] font-semibold leading-tight tracking-[-0.03em] text-ink">Runs</h1>
      <p className="mt-3 text-sm text-muted">Every run, newest first.</p>

      <div className="mt-10">
        {error && <p className="text-sm text-fail">Could not load runs: {error}</p>}
        {runs === null && !error && <p className="text-sm text-muted">Loading</p>}
        {runs?.length === 0 && (
          <p className="text-sm text-muted">
            No runs yet.{" "}
            <a href="#/" className="text-ink underline-offset-2 hover:underline">
              Start from home
            </a>
            .
          </p>
        )}
        {runs && runs.length > 0 && <RunsTable runs={runs} />}
      </div>
    </div>
  );
}
