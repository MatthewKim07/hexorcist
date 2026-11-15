import { CircleHelp } from "lucide-react";
import { SpecAmbiguity as Item } from "../api";
import { iconProps } from "../icons";

/**
 * Checks that fail on the uploaded firmware and fail the same way on an implementation written from the
 * spec alone. They are not reported as bugs and not used as fix targets: the check or the spec is the
 * likelier problem. Both measurements are shown so the reader can judge.
 */
export function SpecAmbiguity({ items }: { items: Item[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <section aria-label="Possible spec ambiguity" className="space-y-3">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-medium text-ink">
          <CircleHelp {...iconProps} className="shrink-0 text-muted" aria-hidden="true" />
          Possible spec ambiguity
        </h3>
        <p className="mt-1 max-w-[72ch] text-xs text-muted">
          These checks fail on your firmware and fail the same way on the implementations written from the spec alone. Either the check or the spec is probably the problem, so they are not counted as bugs.
        </p>
      </div>
      {items.map((u) => (
        <article key={u.assertion_id} className="border border-line bg-white p-4" style={{ borderRadius: 8 }}>
          <p className="text-sm text-ink">{u.requirement}</p>
          {u.spec_quote && <p className="mt-1 max-w-[72ch] text-xs italic text-muted">“{u.spec_quote}”</p>}
          <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-muted">Your firmware</dt>
              <dd className="mt-1 font-mono text-ink">{u.your_firmware || "—"}</dd>
            </div>
            {(u.clean_rooms?.length ?? 0) > 1 ? (
              u.clean_rooms!.map((r, i) => (
                <div key={i}>
                  <dt className="text-muted">Clean-room implementation {i + 1}</dt>
                  <dd className="mt-1 font-mono text-ink">{r.evidence || "—"}</dd>
                </div>
              ))
            ) : (
              <div>
                <dt className="text-muted">Clean-room implementation</dt>
                <dd className="mt-1 font-mono text-ink">{u.clean_room || "—"}</dd>
              </div>
            )}
          </dl>
          <p className="mt-3 text-xs text-muted">
            Scenario: {u.scenario_name}. Failed in {u.failing_scenarios} scenario{u.failing_scenarios === 1 ? "" : "s"}, and in {u.shared_scenarios} of them the clean-room version{(u.clean_rooms?.length ?? 0) > 1 ? "s" : ""} failed it the same way.
          </p>
        </article>
      ))}
    </section>
  );
}
