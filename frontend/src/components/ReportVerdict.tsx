import { Box, Bug, CircleCheck, CircleHelp, CircleX, Clock, FlaskConical, LucideIcon, ShieldCheck } from "lucide-react";
import { Report } from "../api";
import { shortDuration } from "../format";
import { iconProps } from "../icons";
import { Tone, TONE_TEXT } from "./Common";

function verdictMeta(status: string): { Icon: LucideIcon; tone: Tone; spin?: boolean } {
  switch (status) {
    case "fixed":
    case "clean":
      return { Icon: CircleCheck, tone: "pass" };
    case "contained":
      return { Icon: ShieldCheck, tone: "pass" };
    case "inconclusive":
    case "interrupted":
    case "blocked":
      return { Icon: CircleHelp, tone: "neutral" };
    default:
      return { Icon: CircleX, tone: "fail" };
  }
}

/** One-sentence verdict for the finished report. */
export function verdictText(report: Report | null, status: string, firstWarning: string): { title: string; detail: string } {
  const s = report?.score;
  const n = s?.bugs_found ?? 0;
  const v = s?.bugs_verified ?? 0;
  const bugs = `${n} bug${n === 1 ? "" : "s"} found`;
  const fixed = v === n ? (n === 1 ? "fixed and verified" : n === 2 ? "both fixed and verified" : "all fixed and verified") : `${v} fixed and verified`;
  switch (status) {
    case "fixed":
      return { title: `${bugs}, ${fixed}`, detail: "" };
    case "clean":
      return { title: "No bugs found", detail: s ? `${s.assertions} checks passed in ${s.scenarios} scenarios` : "" };
    case "partial":
      return { title: `${bugs}, ${v} fixed and verified`, detail: "The best patch still fails a check, so it is not claimed as a fix" };
    case "unfixed":
      return { title: `${bugs}, no working fix`, detail: "" };
    case "inconclusive":
      return { title: "Inconclusive", detail: firstWarning || "Not everything could be checked" };
    case "compile_failed":
      return { title: "Does not compile", detail: "" };
    case "contained": {
      const passed = s?.checks_passed ?? 0;
      const total = s?.checks_total ?? 0;
      return { title: `Contained · ${passed}/${total} checks`, detail: "" };
    }
    case "containment_failed":
      return { title: "Not contained", detail: "A containment check failed" };
    case "blocked":
      return { title: "Blocked by the input guard", detail: "No LLM call was made" };
    case "interrupted":
      return { title: "Interrupted", detail: "The backend restarted during the run" };
    case "error":
      return { title: "The run failed", detail: report?.error ?? "" };
    default:
      return { title: status, detail: "" };
  }
}

function Stat({ Icon, value, label }: { Icon: LucideIcon; value: string | number; label: string }) {
  return (
    <div className="border border-line bg-white p-4" style={{ borderRadius: 8 }}>
      <div className="mb-2 text-muted">
        <Icon {...iconProps} />
      </div>
      <div className="text-2xl font-semibold tracking-tight text-ink">{value}</div>
      <div className="mt-1 text-xs text-muted">{label}</div>
    </div>
  );
}

/** Verdict heading + four stat tiles under the header card. */
export function ReportVerdict({
  report,
  status,
  firstWarning,
  createdAt,
  finishedAt,
}: {
  report: Report | null;
  status: string;
  firstWarning: string;
  createdAt: number;
  finishedAt: number | null;
}) {
  const { title, detail } = verdictText(report, status, firstWarning);
  const meta = verdictMeta(status);
  const color = TONE_TEXT[meta.tone];
  const score = report?.score;
  const contained = !!report?.contained;
  const dur = shortDuration(createdAt, finishedAt) || "—";

  const tiles = contained
    ? [
        { Icon: CircleCheck, value: `${score?.checks_passed ?? 0}/${score?.checks_total ?? 0}`, label: "checks passed" },
        { Icon: ShieldCheck, value: report?.containment?.secrets_found ?? 0, label: "secrets found" },
        { Icon: Box, value: `${report?.containment?.removed ?? 0}/${report?.containment?.total ?? 0}`, label: "containers removed" },
        { Icon: Clock, value: dur, label: "duration" },
      ]
    : [
        { Icon: Bug, value: score?.bugs_found ?? 0, label: "bugs found" },
        { Icon: FlaskConical, value: score?.scenarios ?? 0, label: "scenarios run" },
        { Icon: Box, value: report?.containment?.total ?? 0, label: "sandboxes" },
        { Icon: Clock, value: dur, label: "duration" },
      ];

  return (
    <section aria-label="Verdict">
      <h2 className={`flex items-start gap-3 text-[28px] font-semibold leading-tight tracking-[-0.03em] sm:text-[32px] ${color}`}>
        <meta.Icon {...iconProps} className="mt-1.5 h-7 w-7 shrink-0 sm:mt-2 sm:h-8 sm:w-8" size={28} strokeWidth={1.5} />
        <span className="text-ink">{title}</span>
      </h2>
      {detail && <p className={`mt-2 text-sm ${meta.tone === "fail" ? "text-fail" : "text-muted"}`}>{detail}</p>}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {tiles.map((t) => (
          <Stat key={t.label} Icon={t.Icon} value={t.value} label={t.label} />
        ))}
      </div>
    </section>
  );
}
