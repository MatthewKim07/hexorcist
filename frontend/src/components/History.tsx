import { useEffect, useState } from "react";
import { api, RunSummary } from "../api";
import { Panel, StatusBadge } from "./Common";

export function History() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.runs().then(setRuns).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Past exorcisms</h1>
      {error && <p className="text-fail">Could not load runs: {error}</p>}
      <Panel>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[13px]">
            <thead className="border-b border-line text-[12px] text-faint">
              <tr>
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Firmware</th>
                <th className="px-4 py-2 font-medium">Mode</th>
                <th className="px-4 py-2 font-medium">Result</th>
                <th className="px-4 py-2 text-right font-medium">Bugs verified</th>
              </tr>
            </thead>
            <tbody>
              {runs?.map((run) => (
                <tr key={run.id} className="cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-raised" onClick={() => (location.hash = `#/runs/${run.id}`)}>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-[12px] text-muted">{new Date(run.created_at * 1000).toLocaleString()}</td>
                  <td className="px-4 py-2">
                    <a href={`#/runs/${run.id}`} className="hover:underline">{run.title}</a>
                  </td>
                  <td className="px-4 py-2 text-muted">{run.mode}</td>
                  <td className="px-4 py-2"><StatusBadge status={run.status} /></td>
                  <td className="px-4 py-2 text-right font-mono">{run.score ? `${run.score.bugs_verified} / ${run.score.bugs_found}` : "?"}</td>
                </tr>
              ))}
              {runs?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-faint">No runs yet. Go possess something.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
