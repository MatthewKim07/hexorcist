import { lazy, Suspense, useEffect, useState } from "react";
import { api, Health } from "./api";
import { Chassis } from "./components/Chassis";
import { Landing } from "./components/Landing";
import { NotFound } from "./components/NotFound";
import { TipProvider } from "./components/ui";

const NewRun = lazy(() => import("./components/NewRun").then((m) => ({ default: m.NewRun })));
const RunsPage = lazy(() => import("./components/RunsPage").then((m) => ({ default: m.RunsPage })));
const RunView = lazy(() => import("./components/RunView").then((m) => ({ default: m.RunView })));

function useHash(): string {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const on = () => {
      setHash(location.hash);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealthError(true));
  }, []);

  // Old Break/Build routes land on the new form.
  useEffect(() => {
    if (hash.startsWith("#/break")) {
      location.replace("#/new");
    } else if (hash.startsWith("#/build")) {
      location.replace("#/new?mode=build");
    }
  }, [hash]);

  const runMatch = /^#\/runs\/([a-z0-9]+)/.exec(hash);
  const known = hash === "" || hash === "#" || hash === "#/" || hash.startsWith("#/runs") || hash.startsWith("#/new") || hash.startsWith("#/break") || hash.startsWith("#/build");
  const route = runMatch ? "run" : hash === "#/runs" || hash.startsWith("#/runs?") ? "runs" : hash.startsWith("#/new") || hash.startsWith("#/break") || hash.startsWith("#/build") ? "new" : known ? "landing" : "notfound";
  const newMode = /[?&]mode=build\b/.test(hash) || hash.startsWith("#/build") ? "build" : "break";

  const started = (id: string) => {
    location.hash = `#/runs/${id}`;
  };

  return (
    <TipProvider>
      <Chassis health={health} healthError={healthError}>
        {healthError && (
          <p className="mb-6 rounded-md border border-fail/30 bg-fail/5 px-3 py-2 text-sm text-fail" role="status">
            The backend is unreachable. Start the API and refresh.
          </p>
        )}
        {route === "landing" && <Landing health={health} onStarted={started} />}
        <Suspense fallback={<p className="pt-8 text-sm text-muted">Loading…</p>}>
          {route === "runs" && <RunsPage backendDown={healthError} />}
          {route === "new" && <NewRun key={newMode} health={health} onStarted={started} initialMode={newMode} />}
          {route === "run" && runMatch && <RunView key={runMatch[1]} runId={runMatch[1]} />}
        </Suspense>
        {route === "notfound" && <NotFound />}
      </Chassis>
    </TipProvider>
  );
}
