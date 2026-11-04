import { RunState } from "../useRun";
import { Scenario } from "../api";
import { Badge, Icon, Panel } from "./Common";

interface Props {
  state: RunState;
  iteration: number;
  onIteration: (n: number) => void;
  selected: string | null;
  onSelect: (id: string) => void;
}

export function ScenarioGrid({ state, iteration, onIteration, selected, onSelect }: Props) {
  const iterations = Object.keys(state.results).map(Number).sort((a, b) => a - b);
  const results = state.results[iteration] ?? {};
  const done = Object.keys(results).length;
  const failed = Object.values(results).filter((r) => !r.passed).length;
  const tiles: Scenario[] = state.scenarios;

  return (
    <Panel
      title={`Attack scenarios: ${done} of ${tiles.length} run${failed ? `, ${failed} failing` : ""}`}
      right={
        iterations.length > 1 ? (
          <div className="flex gap-1" role="tablist" aria-label="Firmware version">
            {iterations.map((n) => (
              <button key={n} role="tab" aria-selected={n === iteration} onClick={() => onIteration(n)} className={`rounded px-2 py-0.5 text-[11px] ${n === iteration ? "bg-halo/15 text-halo" : "text-muted hover:text-ink"}`}>
                {n === 0 ? "Original" : `Patch ${n}`}
              </button>
            ))}
          </div>
        ) : undefined
      }
    >
      <div className="grid gap-2 p-3 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map((s) => {
          const r = results[s.id];
          const tone = !r ? "border-line" : r.passed ? "border-pass/40 bg-pass/5" : "border-fail/50 bg-fail/10";
          return (
            <button key={s.id} onClick={() => onSelect(s.id)} title={s.hypothesis} className={`min-w-0 rounded-md border p-2 text-left transition-colors hover:border-faint ${tone} ${selected === s.id ? "ring-1 ring-halo/70" : ""}`}>
              <div className="flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0">
                  {!r && <span className="pulse-soft block h-3 w-3 rounded-full bg-line" aria-label="pending" />}
                  {r && (r.passed ? <Icon name="check" className="text-pass" /> : <Icon name="x" className="text-fail" />)}
                </span>
                <span className="min-w-0 flex-1 text-[12px] font-medium leading-snug">{s.name}</span>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1 pl-5">
                <Badge>{s.source === "llm" ? "agent" : "built-in"}</Badge>
                {r && !r.passed && <Badge tone="fail">{r.failed.length ? `${r.failed.length} failed` : r.exit_reason}</Badge>}
                {r && r.exit_reason !== "completed" && <Badge tone="warn">{r.exit_reason}</Badge>}
              </div>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}
