import { useState } from "react";
import { ArrowRight, Check, ChevronDown, CircleCheck, CircleX, Copy, FileDiff, Ruler } from "lucide-react";
import { AssertionDef, Bug, PinSpec, Report } from "../api";
import { anchorOf, chipLabel, shortRole } from "../checks";
import { chipEvidence } from "../format";
import { iconProps } from "../icons";
import { DiffView } from "./Common";
import { Collapsible, Tooltip } from "./ui";

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

function evidenceChip(label: string, text: string, tone: "fail" | "pass") {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-xs ${tone === "fail" ? "border-fail/30 bg-fail/10 text-fail" : "border-pass/30 bg-pass/10 text-pass"}`}>
      {label}: {text}
    </span>
  );
}

/** One card per bug: title, before→after chips, rule, expandable cause + patch hunk. */
export function BugList({ bugs, report, assertions, pins, focusId, onFocus, open, onOpen }: Props) {
  const fix = report?.fix;
  const [patchOpen, setPatchOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const byRule = new Map<string, Bug[]>();
  for (const bug of bugs) {
    byRule.set(bug.assertion_id, [...(byRule.get(bug.assertion_id) ?? []), bug]);
  }
  const before = report?.matrix?.["0"] ?? {};
  const held = assertions.filter((a) => !byRule.has(a.id) && Object.values(before).every((rs) => !rs.some((r) => r.assertion_id === a.id && r.status === "fail")));

  const copyPatch = async () => {
    if (!fix?.diff.unified) {
      return;
    }
    try {
      await navigator.clipboard.writeText(fix.diff.unified);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be denied.
    }
  };

  return (
    <section aria-label="Bugs" className="space-y-4">
      {bugs.map((bug) => {
        const rule = assertions.find((a) => a.id === bug.assertion_id);
        const isOpen = open === bug.id;
        const outPin = rule?.output_pin || (rule && anchorOf(rule) !== "usb" ? anchorOf(rule) : "");
        const subject = outPin ? shortRole(pins.find((p) => p.pin === outPin), outPin) : "";
        const beforeN = chipEvidence(bug.assertion_type, bug.before?.evidence ?? bug.evidence, subject);
        const afterN = bug.after?.status === "pass" ? chipEvidence(bug.assertion_type, bug.after.evidence, subject) : "";
        const fixed = bug.verified;
        return (
          <Collapsible.Root
            key={bug.id}
            open={isOpen}
            onOpenChange={(next) => {
              onOpen(next ? bug.id : null);
              onFocus(bug);
            }}
          >
            <article id={`bug-${bug.id}`} className={`scroll-mt-24 border border-line bg-white p-4 ${focusId === bug.id ? "border-ink/40" : ""}`} style={{ borderRadius: 8 }}>
              <Collapsible.Trigger className="flex w-full items-start gap-3 text-left">
                {fixed ? <CircleCheck {...iconProps} className="mt-0.5 shrink-0 text-pass" /> : <CircleX {...iconProps} className={`mt-0.5 shrink-0 ${report ? "text-fail" : "text-muted"}`} />}
                <div className="min-w-0 flex-1">
                  <h3 className="text-sm font-medium text-ink">{bug.title}</h3>
                  <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5">
                    <span className="inline-flex items-center gap-2">
                      {evidenceChip("Before", beforeN || "—", "fail")}
                      <ArrowRight {...iconProps} className="shrink-0 text-muted" aria-hidden="true" />
                    </span>
                    {afterN ? evidenceChip("After", afterN, "pass") : <span className="font-mono text-xs text-muted">After: —</span>}
                  </div>
                  {rule && (
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
                      <Ruler {...iconProps} className="shrink-0" />
                      <span className="min-w-0 truncate">{chipLabel(rule, pins)}</span>
                    </p>
                  )}
                </div>
                <ChevronDown {...iconProps} className={`mt-0.5 shrink-0 text-muted transition-transform ${isOpen ? "rotate-180" : ""}`} />
              </Collapsible.Trigger>
              <Collapsible.Content className="fold">
                <div className="mt-3 space-y-3 border-t border-line pt-3 pl-7 text-sm">
                  {bug.root_cause && (
                    <p className="max-w-[72ch] text-muted">
                      {bug.root_cause}
                      {bug.code_lines.length > 0 && <span className="num ml-2 text-xs">line {bug.code_lines.join(", ")}</span>}
                    </p>
                  )}
                  {bug.failing_scenarios.length > 1 && <p className="text-xs text-muted">Fails in {bug.failing_scenarios.length} scenarios</p>}
                </div>
              </Collapsible.Content>
            </article>
          </Collapsible.Root>
        );
      })}

      {report && held.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted">
          <span>Held in every scenario</span>
          {held.map((a) => (
            <span key={a.id} className="inline-flex items-center gap-1.5 text-ink">
              <CircleCheck {...iconProps} className="text-pass" />
              {chipLabel(a, pins)}
            </span>
          ))}
        </p>
      )}

      {fix && (
        <Collapsible.Root open={patchOpen} onOpenChange={setPatchOpen}>
          <div className="border border-line bg-white" style={{ borderRadius: 8 }}>
            <div className="flex items-center gap-2 px-4 py-3">
              <Collapsible.Trigger className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm text-ink">
                <FileDiff {...iconProps} className="shrink-0 text-muted" />
                <span className="font-medium">Patch</span>
                <span className="num text-xs text-muted">
                  +{fix.diff.added} −{fix.diff.removed}
                </span>
                <ChevronDown {...iconProps} className={`ml-auto shrink-0 text-muted transition-transform ${patchOpen ? "rotate-180" : ""}`} />
              </Collapsible.Trigger>
              <Tooltip content={copied ? "Copied" : "Copy patch"}>
                <button type="button" aria-label="Copy patch" className="key inline-flex h-8 w-8 items-center justify-center rounded-md border border-line text-muted hover:text-ink" onClick={copyPatch}>
                  {copied ? <Check {...iconProps} /> : <Copy {...iconProps} />}
                </button>
              </Tooltip>
            </div>
            <Collapsible.Content className="fold">
              <div className="space-y-3 border-t border-line px-4 py-3">
                {fix.summary && <p className="max-w-[72ch] text-sm text-muted">{fix.summary}</p>}
                <DiffView unified={fix.diff.unified} />
              </div>
            </Collapsible.Content>
          </div>
        </Collapsible.Root>
      )}
    </section>
  );
}
