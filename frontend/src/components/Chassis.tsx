import { createContext, FormEvent, ReactNode, useCallback, useContext, useRef, useState } from "react";
import * as RDialog from "@radix-ui/react-dialog";
import * as RPopover from "@radix-ui/react-popover";
import { getPasscode, Health, isPasscodeError, setPasscode } from "../api";
import { Logo } from "./Logo";

type PasscodeGate = <T>(action: () => Promise<T>) => Promise<T>;

const PasscodeGateCtx = createContext<PasscodeGate>(async (action) => action());

/** Wrap an API action so a missing/wrong passcode opens the dialog, then retries once. */
export function usePasscodeGate(): PasscodeGate {
  return useContext(PasscodeGateCtx);
}

function healthTone(health: Health | null, healthError: boolean): "green" | "amber" | "red" {
  if (healthError || !health) {
    return "red";
  }
  if (health.ok && health.llm_configured) {
    return "green";
  }
  return "amber";
}

function healthSummary(health: Health | null, healthError: boolean): string {
  if (healthError || !health) {
    return "Backend unreachable";
  }
  const sandbox = health.ok ? "Sandbox ready" : "Sandbox down";
  const model = health.llm_configured ? health.llm_model : "No model";
  return `${sandbox} · ${model}`;
}

function PasscodeDialog({ open, onOpenChange, onContinue }: { open: boolean; onOpenChange: (v: boolean) => void; onContinue: (value: string) => void }) {
  const [value, setValue] = useState(() => getPasscode());
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const next = value.trim();
    setPasscode(next);
    onContinue(next);
  };

  return (
    <RDialog.Root
      open={open}
      onOpenChange={(v) => {
        if (v) {
          setValue(getPasscode());
        }
        onOpenChange(v);
      }}
    >
      <RDialog.Portal>
        <RDialog.Overlay className="scrim fixed inset-0 z-40 bg-ink/20" />
        <RDialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-[min(360px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-line bg-white p-5 shadow-[0_12px_40px_rgba(23,23,23,0.16)] outline-none"
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            inputRef.current?.focus();
            inputRef.current?.select();
          }}
        >
          <RDialog.Title className="text-base font-semibold text-ink">Enter the demo passcode</RDialog.Title>
          <RDialog.Description className="mt-1 text-sm text-muted">Required to start a run on this demo.</RDialog.Description>
          <form className="mt-4 space-y-4" onSubmit={submit}>
            <input
              ref={inputRef}
              type="password"
              autoComplete="current-password"
              className="form-input w-full"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Passcode"
            />
            <div className="flex justify-end gap-2">
              <RDialog.Close type="button" className="btn-ghost text-sm">
                Cancel
              </RDialog.Close>
              <button type="submit" className="btn-primary">
                Continue
              </button>
            </div>
          </form>
        </RDialog.Content>
      </RDialog.Portal>
    </RDialog.Root>
  );
}

function HealthDot({ health, healthError, onPasscode }: { health: Health | null; healthError: boolean; onPasscode: () => void }) {
  const tone = healthTone(health, healthError);
  const summary = healthSummary(health, healthError);
  const color = tone === "green" ? "bg-pass" : tone === "amber" ? "bg-[#D97706]" : "bg-fail";

  return (
    <RPopover.Root>
      <RPopover.Trigger asChild>
        <button type="button" aria-label={summary} className="flex h-6 w-6 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ink/20">
          <span className={`h-2 w-2 rounded-full ${color}`} />
        </button>
      </RPopover.Trigger>
      <RPopover.Portal>
        <RPopover.Content side="bottom" align="end" sideOffset={8} className="pop z-50 w-[240px] rounded-lg border border-line bg-white p-3 text-sm shadow-[0_8px_24px_rgba(23,23,23,0.12)] outline-none">
          <p className="text-ink">{summary}</p>
          <RPopover.Close asChild>
            <button type="button" className="mt-2 text-sm text-muted transition-colors hover:text-ink" onClick={onPasscode}>
              Passcode
            </button>
          </RPopover.Close>
        </RPopover.Content>
      </RPopover.Portal>
    </RPopover.Root>
  );
}

/** App shell: top bar, centered page, health dot and passcode dialog. */
export function Chassis({ health, healthError, children }: { health: Health | null; healthError: boolean; children: ReactNode }) {
  const [passOpen, setPassOpen] = useState(false);
  const waiter = useRef<{ resolve: () => void; reject: (e: Error) => void } | null>(null);

  const openPasscode = useCallback(() => {
    setPassOpen(true);
  }, []);

  const requestPasscode = useCallback(() => {
    return new Promise<void>((resolve, reject) => {
      waiter.current = { resolve, reject };
      setPassOpen(true);
    });
  }, []);

  const withPasscode = useCallback<PasscodeGate>(
    async (action) => {
      try {
        return await action();
      } catch (e) {
        if (!isPasscodeError(e)) {
          throw e;
        }
        await requestPasscode();
        return await action();
      }
    },
    [requestPasscode],
  );

  const onContinue = () => {
    setPassOpen(false);
    waiter.current?.resolve();
    waiter.current = null;
  };

  const onPassOpenChange = (v: boolean) => {
    setPassOpen(v);
    if (!v && waiter.current) {
      const err = new Error("Passcode cancelled");
      waiter.current.reject(err);
      waiter.current = null;
    }
  };

  return (
    <PasscodeGateCtx.Provider value={withPasscode}>
      <div className="flex min-h-dvh flex-col bg-white text-ink">
        <header className="sticky top-0 z-30 h-14 border-b border-line bg-white">
          <div className="mx-auto flex h-full max-w-[1100px] items-center justify-between px-6">
            <a href="#/" aria-label="Hexorcist, home" className="flex items-center gap-2 text-ink">
              <Logo size={22} />
              <span className="text-sm font-semibold leading-none tracking-tight">Hexorcist</span>
            </a>
            <nav className="flex items-center gap-4 text-sm text-muted">
              <HealthDot health={health} healthError={healthError} onPasscode={openPasscode} />
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
      </div>
      <PasscodeDialog open={passOpen} onOpenChange={onPassOpenChange} onContinue={onContinue} />
    </PasscodeGateCtx.Provider>
  );
}
