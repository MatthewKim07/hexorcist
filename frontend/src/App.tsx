import { useEffect, useState } from "react";
import { api, getPasscode, Health, setPasscode } from "./api";
import { BreakForm } from "./components/BreakForm";
import { BuildForm } from "./components/BuildForm";
import { Logo } from "./components/Common";
import { History } from "./components/History";
import { RunView } from "./components/RunView";
import { Tip, TipProvider } from "./components/ui";

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
  const [code, setCode] = useState(getPasscode());

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealthError(true));
  }, []);

  const runMatch = /^#\/runs\/([a-z0-9]+)/.exec(hash);
  const route = runMatch ? "run" : hash.startsWith("#/runs") ? "runs" : hash.startsWith("#/build") ? "build" : "break";
  const started = (id: string) => {
    location.hash = `#/runs/${id}`;
  };
  const tab = (href: string, label: string, active: boolean) => (
    <a href={href} aria-current={active ? "page" : undefined} className={`rounded-md px-2 py-1.5 text-sm transition-colors sm:px-3 ${active ? "font-medium text-ink" : "hover-ink text-muted"}`}>
      {label}
    </a>
  );
  const ready = health?.ok && health.llm_configured;

  return (
    <TipProvider>
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-bg">
        <div className="mx-auto flex min-h-[57px] max-w-[1008px] flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 sm:gap-x-6 sm:px-6">
          <a href="#/" aria-label="Hexorcist" className="flex items-center gap-2.5">
            <Logo size={22} />
            <span className="hidden text-sm font-semibold tracking-tight sm:inline">Hexorcist</span>
          </a>
          <nav className="flex gap-1" aria-label="Main">
            {tab("#/", "Break", route === "break")}
            {tab("#/build", "Build", route === "build")}
            {tab("#/runs", "History", route === "runs")}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-xs text-muted sm:gap-4">
            {health?.passcode_required && (
              <input
                aria-label="Demo passcode"
                type="password"
                className="field w-24 py-1.5 text-xs sm:w-32"
                placeholder="Passcode"
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setPasscode(e.target.value);
                }}
              />
            )}
            {health && (
              <Tip side="bottom" content={health.ok ? `Sandbox ready. Model: ${health.llm_configured ? `${health.llm_model} at ${health.llm_base_url}` : "not configured"}` : health.sandbox.error || "Sandbox down"}>
                <span tabIndex={0} className="flex items-center gap-2 rounded text-muted">
                  <span className={`h-1.5 w-1.5 rounded-full ${ready ? "bg-pass" : "bg-fail"}`} />
                  <span className="hidden sm:inline">{!health.ok ? "Sandbox down" : health.llm_configured ? health.llm_model : "No model key"}</span>
                </span>
              </Tip>
            )}
            {healthError && <span className="text-fail">Backend unreachable</span>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1008px] px-4 py-10 sm:px-6">
        {health && !health.llm_configured && route !== "run" && route !== "runs" && (
          <div className="mb-6 text-xs text-muted">
            No LLM key set. Only the containment demo will run.
          </div>
        )}
        {route === "break" && <BreakForm onStarted={started} />}
        {route === "build" && <BuildForm onStarted={started} />}
        {route === "runs" && <History />}
        {route === "run" && runMatch && <RunView key={runMatch[1]} runId={runMatch[1]} />}
      </main>
    </div>
    </TipProvider>
  );
}
