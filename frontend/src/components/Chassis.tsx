import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import * as RDialog from "@radix-ui/react-dialog";
import { getPasscode, Health, setPasscode } from "../api";
import { History } from "./History";
import { Logo } from "./Logo";
import { Tip } from "./ui";

const StripText = createContext<(text: string) => void>(() => undefined);

/** Status line for the strip; pages call this, the strip shows it. */
export function useStripText(text: string) {
  const set = useContext(StripText);
  useEffect(() => {
    set(text);
  }, [set, text]);
}

export type Mode = "break" | "build";

function StatusStrip({ health, healthError, text, onHistory }: { health: Health | null; healthError: boolean; text: string; onHistory: () => void }) {
  const [code, setCode] = useState(getPasscode());
  const ready = health?.ok && health.llm_configured;
  return (
    <footer className="border-t border-line bg-white">
      <div className="mx-auto flex min-h-[48px] max-w-[1100px] flex-wrap items-center gap-x-5 gap-y-2 px-6 py-2 text-xs text-muted">
        {healthError && (
          <span className="flex items-center gap-2 text-fail">
            <span className="h-1.5 w-1.5 rounded-full bg-fail" />
            Backend unreachable
          </span>
        )}
        {health && (
          <>
            <Tip content={health.ok ? "Compiles and emulations run in sealed, throwaway containers." : health.sandbox.error || "The sandbox image or Docker is missing."}>
              <span tabIndex={0} className="flex items-center gap-2 rounded">
                <span className={`h-1.5 w-1.5 rounded-full ${health.ok ? "bg-pass" : "bg-fail"}`} />
                {health.ok ? "Sandbox" : "Sandbox down"}
              </span>
            </Tip>
            <Tip content={health.llm_configured ? `${health.llm_model} at ${health.llm_base_url}` : "No model key is set, so only the containment test runs."}>
              <span tabIndex={0} className="flex min-w-0 items-center gap-2 rounded">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${ready ? "bg-pass" : "bg-fail"}`} />
                <span className="num truncate">{health.llm_configured ? health.llm_model : "No model key"}</span>
              </span>
            </Tip>
            {health.passcode_required && (
              <label className="flex items-center gap-2">
                <span>Passcode</span>
                <input
                  type="password"
                  className="field num w-24 !py-1 text-xs sm:w-28"
                  value={code}
                  onChange={(e) => {
                    setCode(e.target.value);
                    setPasscode(e.target.value);
                  }}
                />
              </label>
            )}
          </>
        )}
        <button type="button" className="btn-ghost !px-0 text-xs" onClick={onHistory}>
          History
        </button>
        <span className="ml-auto text-ink" aria-live="polite">
          {text}
        </span>
      </div>
    </footer>
  );
}

function HistoryDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <RDialog.Root open={open} onOpenChange={onOpenChange}>
      <RDialog.Portal>
        <RDialog.Overlay className="scrim fixed inset-0 z-40 bg-ink/20" />
        <RDialog.Content className="drawer fixed inset-y-0 right-0 z-50 flex w-[min(440px,100vw)] flex-col border-l border-line bg-white shadow-[-12px_0_32px_rgba(23,23,23,0.12)] outline-none">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <RDialog.Title className="text-base font-semibold">History</RDialog.Title>
            <RDialog.Close className="btn-ghost -mr-2 text-sm">Close</RDialog.Close>
          </div>
          <RDialog.Description className="sr-only">Every run, newest first.</RDialog.Description>
          <div className="scroll min-h-0 flex-1 overflow-y-auto px-5">
            <History onOpen={() => onOpenChange(false)} />
          </div>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}

/** App shell: top bar, centered page, status strip. Existing pages keep working inside. */
export function Chassis({ health, healthError, historyOpen, onHistory, children }: { health: Health | null; healthError: boolean; historyOpen: boolean; onHistory: (open: boolean) => void; children: ReactNode }) {
  const [text, setText] = useState("");
  return (
    <StripText.Provider value={setText}>
      <div className="flex min-h-dvh flex-col bg-white text-ink">
        <header className="sticky top-0 z-30 h-14 border-b border-line bg-white">
          <div className="mx-auto flex h-full max-w-[1100px] items-center justify-between px-6">
            <a href="#/" aria-label="Hexorcist, home" className="flex items-center gap-2 text-ink">
              <Logo size={22} />
              <span className="text-sm font-semibold leading-none tracking-tight">Hexorcist</span>
            </a>
            <nav className="flex items-center gap-5 text-sm text-muted">
              <a href="#/runs" className="hover-ink transition-colors">
                Runs
              </a>
              <a href="https://github.com/MatthewKim07/hexorcist" target="_blank" rel="noreferrer" className="hover-ink transition-colors">
                GitHub
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1100px] flex-1 px-6 pb-16 pt-16">{children}</main>
        <StatusStrip health={health} healthError={healthError} text={text} onHistory={() => onHistory(true)} />
      </div>
      <HistoryDrawer open={historyOpen} onOpenChange={onHistory} />
    </StripText.Provider>
  );
}
