import { useState } from "react";
import { Bug, Report } from "../api";
import { keyNumber } from "../format";
import { DiffView, Icon } from "./Common";

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
            <li key={bug.id}>
              <button
                aria-expanded={isOpen}
                className="grid w-full grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 py-3.5 text-left hover:bg-raised/60 sm:grid-cols-[16px_minmax(0,1fr)_auto_96px]"
                onClick={() => {
                  setOpen(isOpen ? null : bug.id);
                  onFocus(bug);
                }}
              >
                <Icon name="chevron" className={`h-3 w-3 text-faint transition-transform ${isOpen ? "rotate-90" : ""}`} />
                <span className={`min-w-0 ${focusId === bug.id ? "font-medium" : ""}`}>{bug.title}</span>
                <span className="num hidden text-muted sm:block">{fact}</span>
                <span className={`flex items-center justify-end gap-1.5 text-[14px] ${bug.verified ? "text-pass" : report ? "text-fail" : "text-faint"}`}>
                  {bug.verified ? (
                    <>
                      <Icon name="check" /> fixed
                    </>
                  ) : report ? (
                    <>
                      <Icon name="x" /> not fixed
                    </>
                  ) : null}
                </span>
              </button>
              {isOpen && (
                <div className="space-y-4 pb-5 pl-[28px] text-[14px]">
                  {bug.root_cause && (
                    <p>
                      {bug.root_cause}
                      {bug.code_lines.length > 0 && <span className="num ml-2 text-faint">line {bug.code_lines.join(", ")}</span>}
                    </p>
                  )}
                  <dl className="grid grid-cols-[56px_minmax(0,1fr)] gap-x-3 gap-y-2">
                    <dt className="text-fail">Before</dt>
                    <dd className="text-muted">{bug.before?.evidence ?? bug.evidence}</dd>
                    <dt className={bug.after?.status === "pass" ? "text-pass" : "text-faint"}>After</dt>
                    <dd className="text-muted">{bug.after?.evidence ?? "No patch passed"}</dd>
                  </dl>
                  {bug.failing_scenarios.length > 1 && <p className="label">Fails in {bug.failing_scenarios.length} scenarios</p>}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {fix && (
        <details className="group border-b border-line">
          <summary className="flex cursor-pointer items-center gap-3 py-3.5 text-muted hover:text-ink">
            <Icon name="chevron" className="h-3 w-3 text-faint transition-transform group-open:rotate-90" />
            <span>Patch</span>
            <span className="num ml-auto text-faint">
              +{fix.diff.added} −{fix.diff.removed}
            </span>
          </summary>
          <div className="space-y-3 pb-5 pl-[28px]">
            {fix.summary && <p className="text-[14px] text-muted">{fix.summary}</p>}
            <DiffView unified={fix.diff.unified} />
          </div>
        </details>
      )}
    </section>
  );
}
