import { useCallback, useEffect, useRef, useState } from "react";
import { api, Bug, Report, Review, ReviewConcern, ReviewState } from "../api";
import { keyFact } from "../format";
import { Icon } from "./Common";

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

interface Row {
  key: string;
  left: ReviewConcern[];
  bug: Bug | null;
}

const VISIBLE = 4;

function Comparison({ review, bugs, report }: { review: Review; bugs: Bug[]; report: Report | null }) {
  const [more, setMore] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const { rows: paired, unmatched } = pair(bugs, review.concerns);
  const verified = bugs.filter((b) => b.verified).length;
  const fix = report?.fix;

  const rows: Row[] = [
    ...paired.map(({ bug, concerns }) => ({ key: bug.id, left: concerns, bug })),
    ...unmatched.map((c, i) => ({ key: `u${i}`, left: [c], bug: null as Bug | null })),
  ];
  const shown = more ? rows : rows.slice(0, VISIBLE);

  return (
    <div>
      <div className="grid grid-cols-2 gap-8 border-b border-line pb-3 text-[14px]">
        <div className="text-muted">Plain LLM review</div>
        <div>Hexorcist measured</div>
      </div>
      <ul>
        {shown.map((row) => {
          const isOpen = open === row.key;
          const first = row.left[0];
          return (
            <li key={row.key} className="border-b border-line">
              <button aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : row.key)} className="grid w-full grid-cols-2 gap-8 py-3.5 text-left hover:bg-raised/60">
                <span className="min-w-0 text-muted">
                  {first ? first.title : <span className="text-faint">Nothing matched</span>}
                  {row.left.length > 1 && <span className="ml-2 text-faint">+{row.left.length - 1}</span>}
                </span>
                <span className="min-w-0">
                  {row.bug ? (
                    <>
                      <span className="block">{row.bug.title}</span>
                      <span className="mt-0.5 flex items-center gap-3">
                        <span className="num text-fail">{keyFact(row.bug.before?.evidence ?? row.bug.evidence)}</span>
                        {row.bug.verified && (
                          <span className="flex items-center gap-1 text-pass">
                            <Icon name="check" /> fixed
                          </span>
                        )}
                      </span>
                    </>
                  ) : (
                    <span className="text-faint">Not measured</span>
                  )}
                </span>
              </button>
              {isOpen && (
                <div className="grid grid-cols-2 gap-8 pb-4 text-[13px] text-muted">
                  <div className="space-y-2">
                    {row.left.map((c, i) => (
                      <p key={i}>
                        {c.detail}
                        {c.lines.length > 0 && <span className="num ml-2 text-faint">line {c.lines.join(", ")}</span>}
                      </p>
                    ))}
                  </div>
                  <div className="space-y-2">{row.bug ? <p>{row.bug.evidence}</p> : <p className="text-faint">No scenario measured this. A guess stays a guess until it is run.</p>}</div>
                </div>
              )}
            </li>
          );
        })}
        {rows.length === 0 && (
          <li className="grid grid-cols-2 gap-8 border-b border-line py-3.5 text-faint">
            <span>{review.verdict === "looks_correct" ? "Nothing flagged" : "No concerns"}</span>
            <span>No check failed</span>
          </li>
        )}
      </ul>
      {rows.length > VISIBLE && (
        <button className="mt-3 text-[13px] text-muted hover:text-ink" onClick={() => setMore(!more)} aria-expanded={more}>
          {more ? "Show fewer" : `Show ${rows.length - VISIBLE} more`}
        </button>
      )}

      <div className="mt-6 grid grid-cols-2 gap-8 text-[14px]">
        <p className="text-muted">
          {review.concerns.length} concern{review.concerns.length === 1 ? "" : "s"} · <span className="num text-ink">0</span> measured · <span className="num text-ink">0</span> fixes tested
        </p>
        <p>
          <span className="num">{bugs.length}</span> measured · <span className="num text-pass">{verified}</span> fixes verified{fix ? <span className="num ml-2 text-faint">+{fix.diff.added} −{fix.diff.removed}</span> : null}
        </p>
      </div>
    </div>
  );
}

export function ComparePanel({ runId, bugs, report, finished }: { runId: string; bugs: Bug[]; report: Report | null; finished: boolean }) {
  const { state, ask, asking, error } = useReview(runId, finished);
  const waiting = asking || state.pending;

  return (
    <div id="compare" className="py-6">
      {state.review ? (
        <Comparison review={state.review} bugs={bugs} report={report} />
      ) : (
        <div className="space-y-3">
          <button className="btn-outline" onClick={ask} disabled={waiting}>
            {waiting ? "Asking the model…" : "Run a plain LLM review"}
          </button>
          <p className="label">One extra LLM call. No compiler, no emulator.</p>
          {error && <p className="text-fail">{error}</p>}
        </div>
      )}
    </div>
  );
}
