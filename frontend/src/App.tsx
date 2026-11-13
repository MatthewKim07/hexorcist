import { useEffect, useState } from "react";
import { api, Health } from "./api";
import { BreakForm } from "./components/BreakForm";
import { BuildForm } from "./components/BuildForm";
import { Chassis, Mode } from "./components/Chassis";
import { Landing } from "./components/Landing";
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
  const [runMode, setRunMode] = useState<Mode | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealthError(true));
  }, []);

  const runMatch = /^#\/runs\/([a-z0-9]+)/.exec(hash);
  const route = runMatch ? "run" : hash.startsWith("#/runs") ? "runs" : hash.startsWith("#/build") ? "build" : hash.startsWith("#/break") ? "break" : "landing";
  const [historyOpen, setHistoryOpen] = useState(route === "runs");
  useEffect(() => {
    if (route === "runs") {
      setHistoryOpen(true);
    }
  }, [route]);

  const started = (id: string) => {
    location.hash = `#/runs/${id}`;
  };
  const mode: Mode | null = route === "build" ? "build" : route === "break" ? "break" : route === "run" ? runMode : null;

  return (
    <TipProvider>
      <Chassis
        mode={mode}
        onMode={(m) => (location.hash = m === "build" ? "#/build" : "#/break")}
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
        {route === "break" && <BreakForm health={health} onStarted={started} />}
        {route === "build" && <BuildForm onStarted={started} />}
        {route === "run" && runMatch && <RunView key={runMatch[1]} runId={runMatch[1]} onMode={setRunMode} />}
      </Chassis>
    </TipProvider>
  );
}
