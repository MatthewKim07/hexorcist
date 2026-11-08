import { useEffect, useState } from "react";
import { api, Trace } from "./api";

/** Loads one scenario trace for one firmware version, and keeps it so toggling Before and After is instant. */
export function useTrace(runId: string, iteration: number, scenarioId: string | null, ready: boolean): { trace: Trace | null; error: string; loading: boolean } {
  const [cache, setCache] = useState<Record<string, Trace>>({});
  const [error, setError] = useState("");
  const key = scenarioId ? `${iteration}:${scenarioId}` : "";

  useEffect(() => {
    if (!scenarioId || cache[key] || !ready) {
      return;
    }
    let stale = false;
    api
      .trace(runId, iteration, scenarioId)
      .then((tr) => {
        if (!stale) {
          setCache((c) => ({ ...c, [key]: tr }));
          setError("");
        }
      })
      .catch((e) => !stale && setError(e.message));
    return () => {
      stale = true;
    };
  }, [runId, iteration, scenarioId, key, ready, cache]);

  const trace = key ? cache[key] ?? null : null;
  return { trace, error, loading: ready && !trace && !error };
}
