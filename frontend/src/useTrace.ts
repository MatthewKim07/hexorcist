import { useEffect, useState } from "react";
import { api, Trace } from "./api";

function isMissingTrace(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err ?? "");
  return /^404\b/.test(msg) || /no trace/i.test(msg);
}

/** Loads one scenario trace for one firmware version, and keeps it so toggling Before and After is instant. */
export function useTrace(
  runId: string,
  iteration: number,
  scenarioId: string | null,
  ready: boolean,
): { trace: Trace | null; error: string; loading: boolean; missing: boolean } {
  const [cache, setCache] = useState<Record<string, Trace>>({});
  const [error, setError] = useState("");
  const [missingKeys, setMissingKeys] = useState<Record<string, true>>({});
  const key = scenarioId ? `${iteration}:${scenarioId}` : "";
  const trace = key ? cache[key] ?? null : null;
  const missing = !!(key && missingKeys[key]);

  useEffect(() => {
    if (!scenarioId || !key || !ready || cache[key] || missingKeys[key]) {
      return;
    }
    let stale = false;
    setError("");
    api
      .trace(runId, iteration, scenarioId)
      .then((tr) => {
        if (!stale) {
          setCache((c) => ({ ...c, [key]: tr }));
          setError("");
        }
      })
      .catch((e) => {
        if (stale) {
          return;
        }
        if (isMissingTrace(e)) {
          setMissingKeys((m) => ({ ...m, [key]: true }));
          setError("");
        } else {
          setError(e instanceof Error ? e.message : String(e));
        }
      });
    return () => {
      stale = true;
    };
    // cache/missingKeys are read to skip duplicate fetches; listing them would re-fire after success.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional
  }, [runId, iteration, scenarioId, key, ready]);

  // Ready with no trace yet is loading until the API confirms missing or returns an error.
  const loading = ready && !!key && !trace && !missing && !error;
  return { trace, error, loading, missing };
}
