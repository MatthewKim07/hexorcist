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
      <div className="grid gap-1.5 p-3 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map((s) => {
          const r = results[s.id];
          const tone = !r ? "border-line" : r.passed ? "border-pass/40 bg-pass/5" : "border-fail/50 bg-fail/10";
          return (
            <button key={s.id} onClick={() => onSelect(s.id)} title={s.hypothesis} className={`flex min-h-[46px] min-w-0 items-center gap-2 rounded-md border px-2 py-1.5 text-left transition-colors hover:border-faint ${tone} ${selected === s.id ? "ring-1 ring-halo/70" : ""}`}>
              <span className="shrink-0">
                {!r && <span className="pulse-soft block h-3.5 w-3.5 rounded-full bg-line" aria-label="pending" />}
                {r && (r.passed ? <Icon name="check" className="h-3.5 w-3.5 text-pass" /> : <Icon name="x" className="h-3.5 w-3.5 text-fail" />)}
              </span>
              <span className="line-clamp-2 min-w-0 flex-1 text-[12px] font-medium leading-snug">{s.name}</span>
              <span className="flex shrink-0 flex-col items-end gap-0.5">
                {r && !r.passed && <Badge tone="fail">{r.failed.length ? `${r.failed.length} failed` : r.exit_reason}</Badge>}
                {r && r.passed && r.exit_reason !== "completed" && <Badge tone="warn">{r.exit_reason}</Badge>}
                <span className="font-mono text-[10px] leading-none text-faint">{s.source === "llm" ? "agent" : "built-in"}</span>
              </span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}
