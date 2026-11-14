import { useEffect, useState } from "react";
import { Activity, Loader2, LucideIcon, Play, ShieldCheck, Siren, Thermometer, ToggleLeft } from "lucide-react";
import { api, Health, Preset, RunSummary } from "../api";
import { iconCardProps, iconProps } from "../icons";
import { usePasscodeGate } from "./Chassis";
import { RunsTable } from "./RunsTable";
import { Tooltip } from "./ui";

/** A run of an example, with the checks the example ships, so the run measures exactly what its chips say. */
export function startPreset(p: Preset, compare = false) {
  return api.start({ mode: "break", title: p.title, firmware: p.firmware, pins: p.pins, behaviour: p.behaviour, compare, ...(p.checks ? { checks: p.checks } : {}) });
}

/** Short card copy for each preset. Tags stay short and mono. Blurb is the icon tooltip. */
const CARD: Record<string, { blurb: string; tag: string; Icon: LucideIcon }> = {
  thermostat: { blurb: "Fan chatters near the threshold", tag: "hysteresis", Icon: Thermometer },
  button: { blurb: "One press toggles the LED many times", tag: "debounce", Icon: ToggleLeft },
  logger: { blurb: "Printed temperature is scaled wrong", tag: "units", Icon: Activity },
  alarm: { blurb: "Short presses never reach the siren", tag: "blocking delay", Icon: Siren },
  containment: { blurb: "Uploads hostile code. Nothing should escape.", tag: "security demo", Icon: ShieldCheck },
};

function DeviceIcon({ id, blurb }: { id: string; blurb: string }) {
  const Icon = CARD[id]?.Icon ?? Activity;
  return (
    <Tooltip content={blurb}>
      <span
        tabIndex={0}
        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line bg-[#FAFAFA] text-ink"
        aria-label={blurb}
      >
        <Icon {...iconCardProps} />
      </span>
    </Tooltip>
  );
}

function RunButton({ title, busy, disabled, onClick }: { title: string; busy: boolean; disabled: boolean; onClick: () => void }) {
  const label = busy ? `Starting ${title}` : `Run ${title}`;
  return (
    <Tooltip content={busy ? "Starting…" : `Run ${title}`}>
      <button
        type="button"
        aria-label={label}
        className="key inline-flex h-8 w-8 shrink-0 items-center justify-center border border-line bg-white text-ink disabled:opacity-50"
        style={{ borderRadius: 8 }}
        disabled={disabled}
        onClick={onClick}
      >
        {busy ? <Loader2 {...iconProps} className="animate-spin" /> : <Play {...iconProps} />}
      </button>
    </Tooltip>
  );
}

export function Landing({ health, onStarted }: { health: Health | null; onStarted: (id: string) => void }) {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [recent, setRecent] = useState<RunSummary[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const withPasscode = usePasscodeGate();

  useEffect(() => {
    api
      .presets()
      .then(setPresets)
      .catch((e) => setError(e.message));
    api
      .runs()
      .then(setRecent)
      .catch(() => setRecent([]));
  }, []);

  const run = async (p: Preset) => {
    setBusyId(p.id);
    setError("");
    try {
      onStarted((await withPasscode(() => startPreset(p))).run_id);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg !== "Passcode cancelled") {
        setError(msg);
      }
      setBusyId(null);
    }
  };

  const canRun = health === null || health.llm_configured;
  const bugs = presets.filter((p) => p.id !== "containment");
  const containment = presets.find((p) => p.id === "containment");
  const recentRows = recent?.slice(0, 5) ?? [];

  return (
    <div>
      <h1 className="text-[32px] font-semibold leading-tight tracking-[-0.03em] text-ink">Break your firmware.</h1>
      <p className="mt-3 text-sm text-muted">Hexorcist attacks your Arduino sketch on an emulated chip, then proves the fix.</p>

      <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {bugs.map((p) => {
          const card = CARD[p.id] ?? { blurb: p.summary, tag: p.id, Icon: Activity };
          const busy = busyId === p.id;
          const disabled = !!busyId || !canRun;
          return (
            <article key={p.id} className="preset-card flex h-full flex-col border border-line bg-white p-5 transition-[border-color] duration-150">
              <DeviceIcon id={p.id} blurb={card.blurb} />
              <h2 className="mt-3 text-sm font-medium text-ink">{p.title}</h2>
              <div className="mt-auto flex items-center justify-between gap-3 pt-4">
                <span className="font-mono text-xs text-muted">{card.tag}</span>
                <RunButton title={p.title} busy={busy} disabled={disabled} onClick={() => run(p)} />
              </div>
            </article>
          );
        })}
      </div>

      {containment && (
        <div className="mt-8">
          <p className="mb-3 text-xs text-muted">Security</p>
          <article className="preset-card flex items-center gap-3 border border-line bg-white p-5 transition-[border-color] duration-150">
            <DeviceIcon id="containment" blurb={CARD.containment.blurb} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-medium text-ink">{containment.title}</h2>
                  <span className="font-mono text-xs text-muted">{CARD.containment.tag}</span>
                </div>
                <RunButton title={containment.title} busy={busyId === containment.id} disabled={!!busyId} onClick={() => run(containment)} />
              </div>
            </div>
          </article>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-fail">{error}</p>}

      {recentRows.length > 0 && (
        <section className="mt-12">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <h2 className="text-sm font-medium text-ink">Recent runs</h2>
            <a href="#/runs" className="text-sm text-muted transition-colors hover:text-ink">
              View all →
            </a>
          </div>
          <RunsTable runs={recentRows} />
        </section>
      )}
    </div>
  );
}
