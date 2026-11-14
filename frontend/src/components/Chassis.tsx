import { createContext, FormEvent, ReactNode, useCallback, useContext, useRef, useState } from "react";
import * as RDialog from "@radix-ui/react-dialog";
import * as RPopover from "@radix-ui/react-popover";
import { Plus } from "lucide-react";
import { getPasscode, Health, isPasscodeError, setPasscode } from "../api";
import { iconProps } from "../icons";
import { Logo } from "./Logo";
import { Tooltip } from "./ui";

function GitHubMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 98 96" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M48.854 0C21.839 0 0 22 0 49.217c0 21.756 13.993 40.172 33.405 46.69 2.427.49 3.316-1.059 3.316-2.362 0-1.141-.08-5.052-.08-9.127-13.59 2.934-16.42-5.867-16.42-5.867-2.184-5.704-5.42-7.17-5.42-7.17-4.448-3.015.324-3.015.324-3.015 4.934.326 7.523 5.052 7.523 5.052 4.367 7.496 11.404 5.378 14.235 4.074.404-3.178 1.699-5.378 3.074-6.6-10.839-1.141-22.243-5.378-22.243-24.283 0-5.378 1.94-9.778 5.014-13.2-.485-1.222-2.184-6.275.486-13.038 0 0 4.125-1.304 13.426 5.052a46.97 46.97 0 0 1 12.214-1.63c4.125 0 8.33.571 12.213 1.63 9.302-6.356 13.427-5.052 13.427-5.052 2.67 6.763.97 11.816.485 13.038 3.155 3.422 5.015 7.822 5.015 13.2 0 18.905-11.404 23.06-22.324 24.283 1.78 1.548 3.316 4.481 3.316 9.126 0 6.6-.08 11.897-.08 13.526 0 1.304.89 2.853 3.316 2.364 19.412-6.52 33.405-24.935 33.405-46.691C97.707 22 75.788 0 48.854 0z"
      />
    </svg>
  );
}

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
        <button type="button" aria-label={summary} className="flex h-6 w-6 items-center justify-center rounded-full">
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
            <nav className="flex items-center gap-3 text-sm text-muted">
              <HealthDot health={health} healthError={healthError} onPasscode={openPasscode} />
              <a href="#/runs" className="hover-ink transition-colors">
                Runs
              </a>
              <Tooltip content="GitHub">
                <a
                  href="https://github.com/MatthewKim07/hexorcist"
                  target="_blank"
                  rel="noreferrer"
                  aria-label="GitHub"
                  className="hover-ink flex h-8 w-8 items-center justify-center rounded-md transition-colors"
                >
                  <GitHubMark />
                </a>
              </Tooltip>
              <a href="#/new" className="btn-primary inline-flex h-8 items-center gap-1.5 !px-3 !py-0 text-sm">
                <Plus {...iconProps} />
                New
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
