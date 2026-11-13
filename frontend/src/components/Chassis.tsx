import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import * as RDialog from "@radix-ui/react-dialog";
import * as RToggle from "@radix-ui/react-toggle-group";
import { getPasscode, Health, setPasscode } from "../api";
import { Logo } from "./Common";
import { History } from "./History";
import { Tip } from "./ui";

const StripText = createContext<(text: string) => void>(() => undefined);

/** What the instrument is doing, shown at the right of the status strip. */
export function useStripText(text: string) {
  const set = useContext(StripText);
  useEffect(() => {
    set(text);
  }, [set, text]);
}

export type Mode = "break" | "build";

/** Break or Build, as a two-position slide switch. */
function ModeSwitch({ mode, onMode }: { mode: Mode | null; onMode: (m: Mode) => void }) {
  return (
    <RToggle.Root type="single" value={mode ?? ""} onValueChange={(v) => v && onMode(v as Mode)} aria-label="Mode" asChild>
      <div className="relative grid grid-cols-2 rounded-full border border-line bg-raised p-[3px] shadow-[inset_0_1px_2px_rgba(18,24,22,0.08)]">
        <span aria-hidden="true" className={`slide-thumb absolute bottom-[3px] left-[3px] top-[3px] w-[calc(50%-3px)] rounded-full bg-ink ${mode ? "" : "opacity-0"}`} style={{ transform: mode === "build" ? "translateX(100%)" : "translateX(0)" }} />
        {(["break", "build"] as Mode[]).map((m) => (
          <RToggle.Item key={m} value={m} className="key relative z-10 min-w-[68px] rounded-full px-4 py-1 text-sm !font-medium text-muted aria-checked:text-bg">
            {m === "break" ? "Break" : "Build"}
          </RToggle.Item>
        ))}
      </div>
    </RToggle.Root>
  );
}

function StatusStrip({ health, healthError, text, onHistory }: { health: Health | null; healthError: boolean; text: string; onHistory: () => void }) {
  const [code, setCode] = useState(getPasscode());
  const ready = health?.ok && health.llm_configured;
  return (
    <footer className="sticky bottom-0 z-20 border-t border-line bg-bg/95 backdrop-blur-sm">
      <div className="flex min-h-[48px] flex-wrap items-center gap-x-5 gap-y-2 px-5 py-2 text-xs text-muted sm:px-8">
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
        <button className="btn-ghost !px-0 text-xs" onClick={onHistory}>
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
        <RDialog.Overlay className="scrim fixed inset-0 z-40 bg-[#121816]/25" />
        <RDialog.Content className="drawer fixed inset-y-0 right-0 z-50 flex w-[min(440px,100vw)] flex-col border-l border-line bg-bg shadow-[-12px_0_32px_rgba(18,24,22,0.12)] outline-none">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <RDialog.Title className="text-base font-semibold">History</RDialog.Title>
            <RDialog.Close className="btn-ghost -mr-2 text-sm">Close</RDialog.Close>
          </div>
          <RDialog.Description className="sr-only">Every run on this instrument, newest first.</RDialog.Description>
          <div className="scroll min-h-0 flex-1 overflow-y-auto px-5">
            <History onOpen={() => onOpenChange(false)} />
          </div>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}

/** The instrument: nameplate and mode switch on the top bezel, the page in the middle, the status strip along the bottom. */
export function Chassis({ mode, onMode, health, healthError, historyOpen, onHistory, children }: { mode: Mode | null; onMode: (m: Mode) => void; health: Health | null; healthError: boolean; historyOpen: boolean; onHistory: (open: boolean) => void; children: ReactNode }) {
  const [text, setText] = useState("");
  return (
    <StripText.Provider value={setText}>
      <div className="chassis flex h-dvh flex-col bg-bg">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 pb-2 pt-4 sm:px-8 sm:pt-5">
          <a href="#/" aria-label="Hexorcist, home" className="flex items-center gap-2 rounded text-ink">
            <Logo size={20} />
            <span className="text-sm font-semibold tracking-tight">Hexorcist</span>
          </a>
          <ModeSwitch mode={mode} onMode={onMode} />
        </div>
        <main className="min-h-0 flex-1 overflow-y-auto px-5 pb-8 pt-3 sm:px-8">{children}</main>
        <StatusStrip health={health} healthError={healthError} text={text} onHistory={() => onHistory(true)} />
        <button onClick={() => onHistory(true)} className="history-handle fixed right-0 top-1/2 z-30 hidden -translate-y-1/2 rounded-l-md border border-r-0 border-line bg-raised px-1.5 py-4 text-xs text-muted hover:text-ink sm:block" aria-label="Open history">
          <span className="[writing-mode:vertical-rl]">History</span>
        </button>
      </div>
      <HistoryDrawer open={historyOpen} onOpenChange={onHistory} />
    </StripText.Provider>
  );
}
