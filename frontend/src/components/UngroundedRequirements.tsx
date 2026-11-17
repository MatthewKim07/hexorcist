import { FileQuestion } from "lucide-react";
import { UngroundedCheck } from "../api";
import { iconProps } from "../icons";

const RULES: Record<string, string> = {
  rate_limit: "Toggle limit",
  hysteresis_band: "Two thresholds",
  debounce: "Debounce",
  range_bound: "Range bound",
  invented_converse: "Opposite state",
};

/**
 * Checks the model wrote that ask for more than the spec bullet they quote. They still ran, so their measurement
 * is shown, but they are not bugs, not fix targets and not part of the verification.
 */
export function UngroundedRequirements({ items }: { items: UngroundedCheck[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <section aria-label="Checks left out" className="space-y-3">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-medium text-ink">
          <FileQuestion {...iconProps} className="shrink-0 text-muted" aria-hidden="true" />
          Left out: asks for more than the spec states
        </h3>
        <p className="mt-1 max-w-[72ch] text-xs text-muted">
          These checks go beyond the spec sentence they quote, so a failure says nothing about your firmware. They are not counted as bugs and the fix loop ignores them.
        </p>
      </div>
      {items.map((u) => (
        <article key={u.assertion_id} className="border border-line bg-white p-4" style={{ borderRadius: 8 }}>
          <p className="text-xs uppercase tracking-wide text-muted">{RULES[u.rule] ?? u.rule}</p>
          <p className="mt-1 text-sm text-ink">{u.requirement}</p>
          {u.spec_quote && <p className="mt-1 max-w-[72ch] text-xs italic text-muted">“{u.spec_quote}”</p>}
          <p className="mt-2 max-w-[72ch] text-xs text-ink">Why: {u.reason}.</p>
          <p className="mt-2 text-xs text-muted">
            {u.failing_scenarios > 0 ? (
              <>
                It failed in {u.failing_scenarios} scenario{u.failing_scenarios === 1 ? "" : "s"}
                {u.scenario_name ? `, first in ${u.scenario_name}` : ""}: <span className="font-mono text-ink">{u.your_firmware || "—"}</span>
              </>
            ) : (
              "It did not fail on your firmware."
            )}
          </p>
        </article>
      ))}
    </section>
  );
}
