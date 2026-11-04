import { useEffect, useState } from "react";
import { api, getPasscode, Health, setPasscode } from "./api";
import { BreakForm } from "./components/BreakForm";
import { BuildForm } from "./components/BuildForm";
import { Badge, Logo } from "./components/Common";
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
    <a href={href} aria-current={active ? "page" : undefined} className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${active ? "bg-raised text-ink" : "text-muted hover:text-ink"}`}>
      {label}
    </a>
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
          <a href="#/" className="flex items-center gap-2.5">
            <Logo />
            <span>
              <span className="block text-[15px] font-semibold leading-tight tracking-tight">Hexorcist</span>
              <span className="block text-[11px] leading-tight text-faint">Cast the bugs out of your firmware.</span>
            </span>
          </a>
          <nav className="flex gap-1" aria-label="Main">
            {tab("#/", "Break", route === "break")}
            {tab("#/build", "Build", route === "build")}
            {tab("#/runs", "History", route === "runs")}
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {health?.passcode_required && (
              <input
                aria-label="Demo passcode"
                type="password"
                className="field w-32 py-1 text-[12px]"
                placeholder="Demo passcode"
                value={code}
                onChange={(e) => {
                  setCode(e.target.value);
                  setPasscode(e.target.value);
                }}
              />
            )}
            {health && (
              <>
                <Badge tone={health.ok ? "pass" : "fail"} icon={health.ok ? "shield" : "x"} title={health.sandbox.error}>
                  sandbox {health.ok ? "ready" : "down"}
                </Badge>
                <Badge tone={health.llm_configured ? "neutral" : "warn"} icon={health.llm_configured ? "dot" : "warn"} title={health.llm_base_url}>
                  {health.llm_configured ? health.llm_model : "no LLM key"}
                </Badge>
              </>
            )}
            {healthError && <Badge tone="fail" icon="x">backend unreachable</Badge>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-4 py-5">
        {health && !health.llm_configured && route !== "run" && route !== "runs" && (
          <div className="mb-4 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-[13px] text-warn">
            No LLM is configured. Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env and restart. The containment demo runs without one.
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
