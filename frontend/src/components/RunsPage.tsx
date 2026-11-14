import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api, RunSummary } from "../api";
import { iconProps } from "../icons";
import { RunsTable } from "./RunsTable";
import { RunsSkeleton } from "./Skeletons";

const PAGE = 20;

/** Full runs list. */
export function RunsPage({ backendDown = false }: { backendDown?: boolean }) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(PAGE);

  useEffect(() => {
    if (backendDown) {
      setRuns([]);
      setError("Backend unreachable");
      return;
    }
    api
      .runs()
      .then(setRuns)
      .catch((e) => setError((e as Error).message));
  }, [backendDown]);

  const shown = runs?.slice(0, visible) ?? [];
  const more = (runs?.length ?? 0) > visible;

  return (
    <div>
      <h1 className="text-[32px] font-semibold leading-tight tracking-[-0.03em] text-ink">Runs</h1>

      <div className="mt-10">
        {backendDown || error ? (
          <p className="text-sm text-fail">Could not load runs. Check that the backend is running.</p>
        ) : runs === null ? (
          <RunsSkeleton />
        ) : runs.length === 0 ? (
          <div className="space-y-4">
            <p className="text-sm text-muted">No runs yet.</p>
            <a href="#/new" className="btn-primary inline-flex h-9 items-center gap-1.5 !px-3 text-sm">
              <Plus {...iconProps} />
              New
            </a>
          </div>
        ) : (
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
