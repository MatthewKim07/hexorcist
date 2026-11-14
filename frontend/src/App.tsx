import { useEffect, useState } from "react";
import { api, Health } from "./api";
import { Chassis } from "./components/Chassis";
import { Landing } from "./components/Landing";
import { NewRun } from "./components/NewRun";
import { RunView } from "./components/RunView";
import { TipProvider } from "./components/ui";

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
  const route = runMatch ? "run" : hash.startsWith("#/runs") ? "runs" : hash.startsWith("#/new") || hash.startsWith("#/break") || hash.startsWith("#/build") ? "new" : "landing";
  const newMode = /[?&]mode=build\b/.test(hash) || hash.startsWith("#/build") ? "build" : "break";
  const [historyOpen, setHistoryOpen] = useState(route === "runs");
  useEffect(() => {
    if (route === "runs") {
      setHistoryOpen(true);
    }
  }, [route]);

  const started = (id: string) => {
    location.hash = `#/runs/${id}`;
  };

  return (
    <TipProvider>
      <Chassis
        health={health}
        healthError={healthError}
        historyOpen={historyOpen}
        onHistory={(open) => {
          setHistoryOpen(open);
          if (!open && route === "runs") {
            location.hash = "#/";
          }
        }}
      >
        {(route === "landing" || route === "runs") && <Landing health={health} onStarted={started} />}
        {route === "new" && <NewRun key={newMode} health={health} onStarted={started} initialMode={newMode} />}
        {route === "run" && runMatch && <RunView key={runMatch[1]} runId={runMatch[1]} />}
      </Chassis>
    </TipProvider>
  );
}
