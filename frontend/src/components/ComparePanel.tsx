import { useCallback, useEffect, useRef, useState } from "react";
import { api, Bug, Report, Review, ReviewConcern, ReviewState } from "../api";
import { Badge, Icon, Panel } from "./Common";

const EMPTY: ReviewState = { review: null, pending: false, error: "" };

/** Loads the stored review once, and polls while the backend is still waiting for the model. */
function useReview(runId: string, ready: boolean) {
  const [state, setState] = useState<ReviewState>(EMPTY);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef<number | undefined>(undefined);

  const load = useCallback(() => {
    api
      .review(runId)
      .then((s) => {
        setState(s);
        if (s.pending) {
          timer.current = window.setTimeout(load, 1500);
        }
      })
      .catch(() => undefined);
  }, [runId]);

  useEffect(() => {
    if (ready) {
      load();
    }
    return () => window.clearTimeout(timer.current);
  }, [ready, load]);

  const ask = async () => {
    setAsking(true);
    setError("");
    try {
      const s = await api.requestReview(runId);
      setState(s);
      window.clearTimeout(timer.current);
      if (s.pending) {
        timer.current = window.setTimeout(load, 1500);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAsking(false);
    }
  };

  return { state, ask, asking, error: error || state.error };
}

const STOP = new Set(["that", "this", "with", "from", "when", "into", "than", "have", "does", "will", "must", "code", "line", "lines", "spec", "firmware", "sensor"]);

function words(text: string): Set<string> {
  return new Set(text.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length >= 4 && !STOP.has(w)));
}

function similarity(c: ReviewConcern, b: Bug): number {
  const lines = new Set(c.lines);
  const union = new Set([...c.lines, ...b.code_lines]);
  const shared = b.code_lines.filter((n) => lines.has(n)).length;
  const jaccard = union.size ? shared / union.size : 0;
  const a = words(`${c.title} ${c.detail}`);
  const w = words(`${b.title} ${b.requirement}`);
  const common = [...a].filter((x) => w.has(x)).length;
  return jaccard + 0.5 * (common / Math.max(1, Math.min(a.size, w.size, 6)));
}

/** Pair each measured bug with the review concerns that most resemble it: cited lines first, then shared words. */
function pair(bugs: Bug[], concerns: ReviewConcern[]) {
  const owner = concerns.map((c) => {
    let best = -1;
    let bestScore = 0.25;
    bugs.forEach((b, i) => {
      const score = similarity(c, b);
      if (score > bestScore) {
        best = i;
        bestScore = score;
      }
    });
    return best;
  });
  return {
    rows: bugs.map((bug, i) => ({ bug, concerns: concerns.filter((_, j) => owner[j] === i) })),
    unmatched: concerns.filter((_, j) => owner[j] === -1),
  };
}

const CONFIDENCE_TONE = { low: "neutral", medium: "warn", high: "warn" } as const;

function Concern({ c, full }: { c: ReviewConcern; full: boolean }) {
  return (
    <div className="rounded-md border border-dashed border-line bg-raised/60 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[13px] font-medium">{c.title}</span>
        <Badge tone={CONFIDENCE_TONE[c.confidence]}>{c.confidence} confidence</Badge>
        <Badge>not measured</Badge>
      </div>
      <p className={`mt-1 text-[12.5px] leading-relaxed text-muted ${full ? "" : "line-clamp-2"}`}>{c.detail}</p>
      {c.lines.length > 0 && <p className="mt-1 font-mono text-[11px] text-faint">Lines {c.lines.join(", ")}</p>}
    </div>
  );
}

function Measured({ bug }: { bug: Bug }) {
  const verified = bug.verified;
  return (
    <div className="rounded-md border border-fail/30 bg-fail/5 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[13px] font-medium">{bug.title}</span>
        <Badge tone="fail" icon="x">
          measured
        </Badge>
        {verified && (
          <Badge tone="pass" icon="check">
            fix verified
          </Badge>
        )}
      </div>
      <p className="mt-1 text-[12.5px] leading-relaxed">{bug.evidence}</p>
      {bug.after?.status === "pass" && <p className="mt-1.5 text-[12.5px] leading-relaxed text-pass">After the fix: {bug.after.evidence}</p>}
    </div>
  );
}

function Empty({ children }: { children: string }) {
  return <div className="rounded-md border border-line/60 px-3 py-2.5 text-[12.5px] text-faint">{children}</div>;
}

function Side({ tone, icon, title, note }: { tone: "guess" | "proof"; icon: "dot" | "check"; title: string; note: string }) {
  return (
    <div className={`border-b px-4 py-2.5 ${tone === "proof" ? "border-pass/30 bg-pass/5" : "border-line bg-raised/50"}`}>
      <div className={`flex items-center gap-1.5 text-[13px] font-semibold ${tone === "proof" ? "text-pass" : "text-muted"}`}>
        <Icon name={icon} /> {title}
      </div>
      <div className="text-[11.5px] text-faint">{note}</div>
    </div>
  );
}

function Comparison({ review, bugs, report }: { review: Review; bugs: Bug[]; report: Report | null }) {
  const [full, setFull] = useState(false);
  const { rows, unmatched } = pair(bugs, review.concerns);
  const verified = bugs.filter((b) => b.verified).length;
  const fix = report?.fix;
  const scenarios = report?.score?.scenarios ?? 0;
  const checks = report?.score?.assertions ?? 0;

  return (
    <div>
      <div className="grid gap-px bg-line md:grid-cols-2">
        <div className="bg-panel">
          <Side tone="guess" icon="dot" title="LLM code review: guesses" note={`${review.model} read the code and spec. No compiler, no emulator.`} />
          <div className="space-y-2 p-3">
            {review.summary && <p className="text-[12.5px] italic leading-relaxed text-muted">“{review.summary}”</p>}
          </div>
        </div>
        <div className="bg-panel">
          <Side tone="proof" icon="check" title="Hexorcist: proves" note="Compiled the sketch and ran it on an emulated ATmega328P in a sealed sandbox." />
          <div className="space-y-2 p-3">
            <p className="text-[12.5px] leading-relaxed text-muted">
              {bugs.length
                ? `${bugs.length} failure${bugs.length === 1 ? "" : "s"} measured across ${scenarios} scenarios and ${checks} checks.`
                : `${checks} checks passed across ${scenarios} scenarios.`}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-px bg-line">
        {rows.map(({ bug, concerns }) => (
          <div key={bug.id} className="grid gap-px md:grid-cols-2">
            <div className="space-y-2 bg-panel p-3">{concerns.length ? concerns.map((c, i) => <Concern key={i} c={c} full={full} />) : <Empty>No concern in the review was matched to this bug.</Empty>}</div>
            <div className="bg-panel p-3">
              <Measured bug={bug} />
            </div>
          </div>
        ))}
        {unmatched.length > 0 && (
          <div className="grid gap-px md:grid-cols-2">
            <div className="space-y-2 bg-panel p-3">
              {unmatched.map((c, i) => (
                <Concern key={i} c={c} full={full} />
              ))}
            </div>
            <div className="bg-panel p-3">
              <Empty>No measured failure on these lines. Either it is not a bug, or no scenario exercised it. A guess stays a guess until it is run.</Empty>
            </div>
          </div>
        )}
        {!rows.length && !unmatched.length && (
          <div className="grid gap-px md:grid-cols-2">
            <div className="bg-panel p-3">
              <Empty>{review.verdict === "looks_correct" ? "The review found nothing to flag." : "No concerns listed."}</Empty>
            </div>
            <div className="bg-panel p-3">
              <Empty>No check failed.</Empty>
            </div>
          </div>
        )}
        <div className="grid gap-px md:grid-cols-2">
          <div className="bg-panel p-3">
            <div className="panel-title mb-1">Suggested fix, never run</div>
            <p className={`whitespace-pre-wrap text-[12.5px] leading-relaxed text-muted ${full ? "" : "line-clamp-4"}`}>{review.suggested_fix || "None given."}</p>
          </div>
          <div className="bg-panel p-3">
            <div className="panel-title mb-1 !text-pass">Verified fix</div>
            {fix ? (
              <p className="text-[12.5px] leading-relaxed">
                {fix.all_passing
                  ? `Patch ${fix.iteration} (+${fix.diff.added} −${fix.diff.removed} lines) was recompiled and re-run against all ${scenarios} scenarios and ${checks} checks: every one passes, nothing regressed.`
                  : `The best patch (+${fix.diff.added} −${fix.diff.removed} lines) still fails some checks, so it is not claimed as a fix.`}
              </p>
            ) : (
              <p className="text-[12.5px] text-faint">{bugs.length ? "No patch was produced." : "Nothing needed fixing."}</p>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line bg-raised/50 px-4 py-2.5 font-mono text-[12px]">
        <span className="text-muted">
          LLM review: {review.concerns.length} concern{review.concerns.length === 1 ? "" : "s"}, <b className="text-ink">0 measured</b>, 0 fixes tested
        </span>
        <span className="text-pass">
          Hexorcist: {bugs.length} bug{bugs.length === 1 ? "" : "s"} measured, <b>{verified} fixes verified</b>
        </span>
        <button className="btn-ghost py-0.5 text-[11px]" onClick={() => setFull(!full)} aria-expanded={full}>
          {full ? "Collapse the review text" : "Show the full review text"}
        </button>
        <span className="ml-auto text-[11px] text-faint">
          1 extra LLM call, {(review.duration_ms / 1000).toFixed(0)} s, {review.tokens} tokens. Rows are paired by cited lines and shared wording.
        </span>
      </div>
    </div>
  );
}

export function ComparePanel({ runId, bugs, report, finished }: { runId: string; bugs: Bug[]; report: Report | null; finished: boolean }) {
  const { state, ask, asking, error } = useReview(runId, finished);
  const waiting = asking || state.pending;

  return (
    <Panel
      title="LLM guesses vs Hexorcist proves"
      right={
        <div className="flex items-center gap-2">
          <Badge>optional</Badge>
          {!state.review && (
            <button className="btn-ghost" onClick={ask} disabled={waiting}>
              {waiting ? "Asking the model…" : "Compare with a plain LLM code review"}
            </button>
          )}
        </div>
      }
    >
      {state.review ? (
        <Comparison review={state.review} bugs={bugs} report={report} />
      ) : (
        <div className="space-y-1 p-4 text-[13px] text-muted">
          <p>
            What does the same model say if it only reads the code? One extra LLM call, same firmware and spec, no emulator. It is shown beside the measured evidence above, clearly labelled as unverified.
          </p>
          {waiting && <p className="pulse-soft text-halo">Waiting for the model…</p>}
          {error && <p className="text-fail">{error}</p>}
        </div>
      )}
    </Panel>
  );
}
