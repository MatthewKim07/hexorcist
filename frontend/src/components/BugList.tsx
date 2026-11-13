import { AssertionDef, Bug, PinSpec, Report } from "../api";
import { chipLabel } from "../checks";
import { keyNumber } from "../format";
import { DiffView, Icon } from "./Common";
import { Collapsible, Fold, Ticking } from "./ui";

interface Props {
  bugs: Bug[];
  report: Report | null;
  assertions: AssertionDef[];
  pins: PinSpec[];
  /** The bug whose scenario is on the board. Clicking a row moves the board to it. */
  focusId: string | null;
  onFocus: (bug: Bug) => void;
  /** The row whose cause is showing. A red rule on the board opens its row too. */
  open: string | null;
  onOpen: (id: string | null) => void;
}

/** Bugs under the check each one broke, then the checks that held. A click shows the board for a bug and opens the cause. */
export function BugList({ bugs, report, assertions, pins, focusId, onFocus, open, onOpen }: Props) {
  const fix = report?.fix;
  const byRule = new Map<string, Bug[]>();
  for (const bug of bugs) {
    byRule.set(bug.assertion_id, [...(byRule.get(bug.assertion_id) ?? []), bug]);
  }
  const before = report?.matrix?.["0"] ?? {};
  const held = assertions.filter((a) => !byRule.has(a.id) && Object.values(before).every((rs) => !rs.some((r) => r.assertion_id === a.id && r.status === "fail")));

  return (
    <section aria-label="Bugs by check" className="space-y-6">
      {[...byRule.entries()].map(([ruleId, group]) => {
        const rule = assertions.find((a) => a.id === ruleId);
        return (
          <div key={ruleId} role="group" aria-labelledby={`rule-${ruleId}`}>
            <h3 id={`rule-${ruleId}`} className="flex items-center gap-2 pb-2 text-sm">
              <span aria-hidden="true" className="h-2 w-2 rounded-full bg-fail" />
              <span className="font-medium">{rule ? chipLabel(rule, pins) : ruleId}</span>
              {rule?.description && <span className="hidden min-w-0 truncate text-muted sm:inline">{rule.description}</span>}
            </h3>
            <ul className="divide-y divide-line border-y border-line">
              {group.map((bug) => {
                const isOpen = open === bug.id;
                const fact = keyNumber(bug.before?.evidence ?? bug.evidence);
                return (
                  <Collapsible.Root
                    asChild
                    key={bug.id}
                    open={isOpen}
                    onOpenChange={(next) => {
                      onOpen(next ? bug.id : null);
                      onFocus(bug);
                    }}
                  >
                    <li id={`bug-${bug.id}`} className="scroll-mt-24">
                      <Collapsible.Trigger className="hover-row grid w-full grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 py-3.5 text-left transition-colors sm:grid-cols-[16px_minmax(0,1fr)_auto_96px]">
                        <Icon name="chevron" className="chev h-3 w-3 text-muted" />
                        <span className={`min-w-0 ${focusId === bug.id ? "font-medium" : ""}`}>{bug.title}</span>
                        <Ticking className="num hidden text-xs text-muted sm:block" text={fact} />
                        <span className={`flex items-center justify-end gap-1.5 text-sm ${bug.verified ? "text-pass" : report ? "text-fail" : "text-muted"}`}>
                          {bug.verified ? (
                            <>
                              <Icon name="check" /> Fixed
                            </>
                          ) : report ? (
                            <>
                              <Icon name="x" /> Not fixed
                            </>
                          ) : null}
                        </span>
                      </Collapsible.Trigger>
                      <Collapsible.Content className="fold">
                        <div className="space-y-4 pb-5 pl-[28px] text-sm">
                          {bug.root_cause && (
                            <p className="max-w-[72ch]">
                              {bug.root_cause}
                              {bug.code_lines.length > 0 && <span className="num ml-2 text-xs text-muted">line {bug.code_lines.join(", ")}</span>}
                            </p>
                          )}
                          <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-3 gap-y-2">
                            <dt className="text-fail">Before</dt>
                            <dd className="text-muted">{bug.before?.evidence ?? bug.evidence}</dd>
                            <dt className={bug.after?.status === "pass" ? "text-pass" : "text-muted"}>After</dt>
                            <dd className="text-muted">{bug.after?.evidence ?? "No patch passed"}</dd>
                          </dl>
                          {bug.failing_scenarios.length > 1 && <p className="label">Fails in {bug.failing_scenarios.length} scenarios</p>}
                        </div>
                      </Collapsible.Content>
                    </li>
                  </Collapsible.Root>
                );
              })}
            </ul>
          </div>
        );
      })}

      {report && held.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted">
          <span>Held in every scenario</span>
          {held.map((a) => (
            <span key={a.id} className="inline-flex items-center gap-1.5">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-pass" />
              {chipLabel(a, pins)}
            </span>
          ))}
        </p>
      )}

      {fix && (
        <div className="border-y border-line py-3.5">
          <Fold
            title={
              <>
                <span>Patch</span>
                <span className="num ml-1 text-xs text-muted">
                  +{fix.diff.added} −{fix.diff.removed}
                </span>
              </>
            }
            contentClassName="space-y-3 pb-2 pl-5"
          >
            {fix.summary && <p className="max-w-[72ch] text-sm text-muted">{fix.summary}</p>}
            <DiffView unified={fix.diff.unified} />
          </Fold>
        </div>
      )}
    </section>
  );
}
