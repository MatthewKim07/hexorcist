import { Bug, Report } from "../api";
import { Badge, DiffView, Icon } from "./Common";

const SEVERITY = {
  critical: "fail",
  high: "fail",
  medium: "warn",
  low: "neutral",
} as const;

export function BugCards({ bugs, report, onReplay }: { bugs: Bug[]; report: Report | null; onReplay: (scenario: string) => void }) {
  if (!bugs.length) {
    return null;
  }
  const fix = report?.fix;
  return (
    <section className="space-y-3">
      <h2 className="panel-title">Bug report</h2>
      {bugs.map((bug) => (
        <article key={bug.id} className="panel p-4">
          <div className="flex flex-wrap items-start gap-2">
            <Badge tone={SEVERITY[bug.severity] ?? "neutral"} icon="warn">
              {bug.severity}
            </Badge>
            <h3 className="min-w-0 flex-1 text-[15px] font-medium leading-snug">{bug.title}</h3>
            {bug.verified ? (
              <Badge tone="pass" icon="check">
                Cast out, verified
              </Badge>
            ) : report ? (
              <Badge tone="warn" icon="dash">
                Not verified
              </Badge>
            ) : null}
          </div>
          <p className="mt-1 text-[13px] text-muted">Requirement: {bug.requirement}</p>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-fail/30 bg-fail/5 p-3">
              <div className="panel-title mb-1 flex items-center gap-1 !text-fail">
                <Icon name="x" /> Measured before fix
              </div>
              <p className="text-[13px] leading-relaxed">{bug.evidence}</p>
            </div>
            <div className={`rounded-md border p-3 ${bug.after?.status === "pass" ? "border-pass/30 bg-pass/5" : "border-line bg-raised"}`}>
              <div className={`panel-title mb-1 flex items-center gap-1 ${bug.after?.status === "pass" ? "!text-pass" : ""}`}>
                {bug.after?.status === "pass" ? <Icon name="check" /> : <Icon name="dash" />} Measured after fix
              </div>
              <p className="text-[13px] leading-relaxed">{bug.after?.evidence ?? "No patch passed verification for this check."}</p>
            </div>
          </div>

          {bug.root_cause && (
            <div className="mt-3">
              <div className="panel-title mb-1">Root cause</div>
              <p className="text-[13px] leading-relaxed text-ink">{bug.root_cause}</p>
              {bug.code_lines.length > 0 && <p className="mt-1 font-mono text-[12px] text-faint">Lines {bug.code_lines.join(", ")}</p>}
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-muted">
            <button className="btn-ghost" onClick={() => onReplay(bug.scenario_id)}>
              <Icon name="play" /> Replay {bug.scenario_name}
            </button>
            <span>
              Failed in {bug.failing_scenarios.length} scenario{bug.failing_scenarios.length === 1 ? "" : "s"}
            </span>
          </div>

          {bug.failing_scenarios.length > 1 && (
            <details className="mt-2 text-[12px]">
              <summary className="cursor-pointer text-muted hover:text-ink">All failing scenarios</summary>
              <ul className="mt-1.5 space-y-1">
                {bug.failing_scenarios.map((s) => (
                  <li key={s.id}>
                    <button className="text-left text-ink underline decoration-line underline-offset-2 hover:decoration-faint" onClick={() => onReplay(s.id)}>
                      {s.name}
                    </button>
                    <span className="text-muted">: {s.evidence}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          {fix && (
            <details className="mt-2 text-[12px]">
              <summary className="cursor-pointer text-muted hover:text-ink">
                Code diff, patch {fix.iteration} (+{fix.diff.added} −{fix.diff.removed})
              </summary>
              <div className="mt-2">
                <DiffView unified={fix.diff.unified} />
              </div>
            </details>
          )}
        </article>
      ))}
    </section>
  );
}
