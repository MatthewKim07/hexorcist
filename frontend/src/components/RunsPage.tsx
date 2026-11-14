import { useEffect, useState } from "react";
import { api, RunSummary } from "../api";
import { RunsTable } from "./RunsTable";

const PAGE = 20;

/** Full runs list, same data the old History drawer used. */
export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(PAGE);

  useEffect(() => {
    api
      .runs()
      .then(setRuns)
      .catch((e) => setError((e as Error).message));
  }, []);

  const shown = runs?.slice(0, visible) ?? [];
  const more = (runs?.length ?? 0) > visible;

  return (
    <div>
      <h1 className="text-[32px] font-semibold leading-tight tracking-[-0.03em] text-ink">Runs</h1>

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
        {runs && runs.length > 0 && (
          <>
            <RunsTable runs={shown} />
            {more && (
              <div className="mt-6 flex justify-center">
                <button type="button" className="key border border-line bg-white px-4 py-2 text-sm !font-normal text-ink" style={{ borderRadius: 8 }} onClick={() => setVisible((n) => n + PAGE)}>
                  Load more
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
