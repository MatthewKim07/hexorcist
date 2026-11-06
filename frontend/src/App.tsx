import { useEffect, useState } from "react";
import { api, getPasscode, Health, setPasscode } from "./api";
import { BreakForm } from "./components/BreakForm";
import { BuildForm } from "./components/BuildForm";
import { Logo } from "./components/Common";
import { History } from "./components/History";
import { RunView } from "./components/RunView";

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
    <a href={href} aria-current={active ? "page" : undefined} className={`rounded-md px-3 py-1.5 text-[14px] transition-colors ${active ? "text-ink" : "text-muted hover:text-ink"}`}>
      {label}
    </a>
  );
  const ready = health?.ok && health.llm_configured;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-bg/95 backdrop-blur">
        <div className="mx-auto flex h-[57px] max-w-[1120px] items-center gap-x-6 px-6">
          <a href="#/" className="flex items-center gap-2.5">
            <Logo />
            <span className="text-[15px] font-semibold tracking-tight">Hexorcist</span>
          </a>
          <nav className="flex gap-1" aria-label="Main">
            {tab("#/", "Break", route === "break")}
            {tab("#/build", "Build", route === "build")}
            {tab("#/runs", "History", route === "runs")}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-[12px] text-faint">
            {health?.passcode_required && (
              <input
                aria-label="Demo passcode"
                type="password"
                className="field w-32 py-1 text-[12px]"
                placeholder="Passcode"
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setPasscode(e.target.value);
                }}
              />
            )}
            {health && (
              <span className="flex items-center gap-2" title={health.ok ? `Sandbox ready. LLM: ${health.llm_configured ? `${health.llm_model} at ${health.llm_base_url}` : "not configured"}` : health.sandbox.error || "Sandbox down"}>
                <span className={`h-1.5 w-1.5 rounded-full ${ready ? "bg-pass" : "bg-fail"}`} />
                <span className="hidden sm:inline">{!health.ok ? "sandbox down" : health.llm_configured ? health.llm_model : "no LLM key"}</span>
              </span>
            )}
            {healthError && <span className="text-fail">backend unreachable</span>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1120px] px-6 py-10">
        {health && !health.llm_configured && route !== "run" && route !== "runs" && (
          <div className="mb-6 text-[13px] text-muted">
            No LLM key set. Only the containment demo will run.
          </div>
        )}
        {route === "break" && <BreakForm onStarted={started} />}
        {route === "build" && <BuildForm onStarted={started} />}
        {route === "runs" && <History />}
        {route === "run" && runMatch && <RunView key={runMatch[1]} runId={runMatch[1]} />}
      </main>
    </div>
  );
}
