import { useState } from "react";
import { Bug, Report } from "../api";
import { keyNumber } from "../format";
import { DiffView, Icon } from "./Common";
import { Collapsible, Fold, Ticking } from "./ui";

interface Props {
  bugs: Bug[];
  report: Report | null;
  /** The bug whose scenario is on the board. Clicking a row moves the board to it. */
  focusId: string | null;
  onFocus: (bug: Bug) => void;
}

/** One line per bug. A click shows the board for it and opens the cause. */
export function BugList({ bugs, report, focusId, onFocus }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const fix = report?.fix;

  return (
    <section aria-label="Bugs">
      <ul className="divide-y divide-line border-y border-line">
        {bugs.map((bug) => {
          const isOpen = open === bug.id;
          const fact = keyNumber(bug.before?.evidence ?? bug.evidence);
          return (
            <Collapsible.Root
              asChild
              key={bug.id}
              open={isOpen}
              onOpenChange={(next) => {
                setOpen(next ? bug.id : null);
                onFocus(bug);
              }}
            >
              <li>
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

      {fix && (
        <div className="border-b border-line py-3.5">
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
