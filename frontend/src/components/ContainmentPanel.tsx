import { useState } from "react";
import { ContainmentRecord, Report } from "../api";
import { Badge, Icon, Panel } from "./Common";

function mb(bytes?: number): string {
  return bytes ? `${Math.round(bytes / 1048576)} MiB` : "?";
}

export function ContainmentPanel({ records, report }: { records: ContainmentRecord[]; report: Report | null }) {
  const [open, setOpen] = useState(false);
  if (!records.length) {
    return null;
  }
  const limits = records[0].limits ?? {};
  const secrets = records.reduce((n, r) => n + r.secrets_found, 0);
  const killed = records.filter((r) => r.timed_out);
  const removed = records.filter((r) => r.removed).length;
  const allNone = records.every((r) => r.limits?.network === "none");
  const reads = [...new Set(records.flatMap((r) => r.violations.filter((v) => v.type === "file_read_attempt").map((v) => v.detail)))];
  const contained = report?.contained;

  return (
    <Panel title="Containment" right={<span className="font-mono text-[11px] text-faint">read back from docker inspect</span>}>
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone={allNone ? "pass" : "fail"} icon="shield">network: {allNone ? "none" : "NOT none"}</Badge>
          <Badge tone={secrets === 0 ? "pass" : "fail"} icon={secrets === 0 ? "check" : "x"}>secrets: {secrets}</Badge>
          <Badge tone={limits.read_only_rootfs ? "pass" : "fail"} icon="check">rootfs: read-only</Badge>
          <Badge tone={limits.cap_drop?.includes("ALL") ? "pass" : "fail"} icon="check">caps: dropped ALL</Badge>
          <Badge tone={limits.no_new_privileges ? "pass" : "fail"} icon="check">no-new-privileges</Badge>
          <Badge tone="pass" icon="check">user: {limits.user}</Badge>
          <Badge tone={!limits.binds?.length && !limits.mounts?.length ? "pass" : "fail"} icon="check">host mounts: {(limits.binds?.length ?? 0) + (limits.mounts?.length ?? 0)}</Badge>
          <Badge>memory: {mb(limits.memory_bytes)}</Badge>
          <Badge>cpu: {(limits.nano_cpus ?? 0) / 1e9}</Badge>
          <Badge>pids: {limits.pids_limit}</Badge>
          <Badge tone={removed === records.length ? "pass" : "warn"} icon="check">containers removed: {removed}/{records.length}</Badge>
          {killed.map((r) => (
            <Badge key={r.container_id} tone="warn" icon="warn">killed at {r.timeout_s}s timeout</Badge>
          ))}
        </div>

        {contained && <ContainedDetail contained={contained} />}

        {!contained && reads.length > 0 && (
          <ul className="space-y-1 text-[13px] text-muted">
            {reads.map((r) => (
              <li key={r} className="flex items-center gap-1.5">
                <Icon name="warn" className="text-warn" /> {r}
              </li>
            ))}
          </ul>
        )}

        <button className="btn-ghost" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Hide" : "Show"} all {records.length} sandbox records
        </button>
        {open && (
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="w-full min-w-[640px] text-left text-[12px]">
              <thead className="border-b border-line text-faint">
                <tr>
                  <th className="px-2.5 py-1.5 font-medium">Task</th>
                  <th className="px-2.5 py-1.5 font-medium">Container</th>
                  <th className="px-2.5 py-1.5 text-right font-medium">Wall time</th>
                  <th className="px-2.5 py-1.5 text-right font-medium">Exit</th>
                  <th className="px-2.5 py-1.5 font-medium">Events</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => (
                  <tr key={`${r.container_id}-${i}`} className="border-b border-line/60 last:border-0">
                    <td className="px-2.5 py-1.5 text-ink">{r.label}</td>
                    <td className="px-2.5 py-1.5 font-mono text-faint">{r.container_id}</td>
                    <td className="px-2.5 py-1.5 text-right font-mono">{(r.duration_ms / 1000).toFixed(1)} s</td>
                    <td className="px-2.5 py-1.5 text-right font-mono">{r.exit_code ?? "?"}</td>
                    <td className="px-2.5 py-1.5">
                      <div className="flex flex-wrap gap-1">
                        {r.timed_out && <Badge tone="warn">timeout kill</Badge>}
                        {r.oom_killed && <Badge tone="warn">OOM kill</Badge>}
                        {r.violations.filter((v) => v.type !== "timeout_kill" && v.type !== "oom_kill").map((v, j) => (
                          <Badge key={j} tone="warn" title={v.detail}>{v.type}</Badge>
                        ))}
                        {!r.violations.length && !r.timed_out && <span className="text-faint">none</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

function ContainedDetail({ contained }: { contained: NonNullable<Report["contained"]> }) {
  const got = contained.what_the_attacker_got;
  return (
    <div className="space-y-3">
      <ul className="grid gap-1.5 md:grid-cols-2">
        {contained.checks.map((c) => (
          <li key={c.label} className={`rounded-md border p-2.5 text-[13px] ${c.ok ? "border-pass/30 bg-pass/5" : "border-fail/40 bg-fail/10"}`}>
            <div className="flex items-center gap-1.5 font-medium">
              {c.ok ? <Icon name="check" className="text-pass" /> : <Icon name="x" className="text-fail" />}
              {c.label}
            </div>
            <p className="mt-0.5 text-[12px] leading-snug text-muted">{c.detail}</p>
          </li>
        ))}
      </ul>

      <div className="rounded-md border border-line bg-raised p-3">
        <h3 className="panel-title mb-1">What the attacker actually got</h3>
        <p className="text-[13px] leading-relaxed">{got.note}</p>
        <dl className="mt-2 grid gap-x-3 gap-y-1 text-[12px] sm:grid-cols-[150px_minmax(0,1fr)]">
          <dt className="font-mono text-faint">/etc/passwd users</dt>
          <dd className="font-mono text-muted">{got.etc_passwd_users.join(" ")}</dd>
          <dt className="font-mono text-faint">/proc/self/environ</dt>
          <dd className="font-mono text-muted">{got.environ_names.join(" ")} (names only)</dd>
          <dt className="font-mono text-faint">~/.ssh/id_rsa</dt>
          <dd className="font-mono text-muted">{got.ssh_key}</dd>
        </dl>
      </div>

      {contained.runaway.ran && (
        <div className="rounded-md border border-warn/30 bg-warn/5 p-3 text-[13px]">
          <div className="flex items-center gap-1.5 font-medium">
            <Icon name="warn" className="text-warn" />
            Runaway firmware: killed at {contained.runaway.duration_s} s
          </div>
          <p className="mt-1 text-muted">{contained.runaway.note}</p>
        </div>
      )}

      <details className="text-[12px]">
        <summary className="cursor-pointer text-muted hover:text-ink">Compiler output from the attack</summary>
        <h4 className="mt-2 text-faint">As uploaded</h4>
        <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-line bg-bg p-2 font-mono text-[11.5px] text-muted">{contained.hostile_compile_log}</pre>
        <h4 className="mt-2 text-faint">Trying to read files back through compiler errors</h4>
        <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-line bg-bg p-2 font-mono text-[11.5px] text-muted">{contained.exfil_compile_log}</pre>
      </details>
    </div>
  );
}

/** The whole containment story in six tiles, readable at a glance on a recording. */
export function ContainedSummary({ report }: { report: Report }) {
  const c = report.contained;
  if (!c) {
    return null;
  }
  const ok = (label: string) => c.checks.find((x) => x.label === label)?.ok ?? false;
  const total = report.containment.total;
  const tiles = [
    {
      ok: ok("Input guard flagged the upload"),
      title: "Guard flagged it",
      stat: `${c.guard.reasons.length} red flags`,
      note: `Risk score ${c.guard.score.toFixed(1)}. Blocked before any model saw it.`,
    },
    {
      ok: ok("LLM never contacted"),
      title: "LLM never saw it",
      stat: "0 LLM calls",
      note: "The prompt injection reached no model.",
    },
    {
      ok: ok("Network disabled"),
      title: "No network",
      stat: `connect ${c.probe.network}, DNS ${c.probe.dns}`,
      note: `NetworkMode none on all ${total} containers.`,
    },
    {
      ok: ok("No control-plane secrets in any output") && ok("No secrets in the sandbox environment"),
      title: "No secrets",
      stat: `${report.containment.secrets_found} found`,
      note: `API key and passcode searched for in all ${total} outputs.`,
    },
    {
      ok: ok("Runaway firmware killed by wall clock"),
      title: "Killed at timeout",
      stat: c.runaway.ran ? `SIGKILL at ${c.runaway.duration_s} s` : "not run",
      note: c.runaway.ran ? `Limit ${c.runaway.timeout_s} s. A firmware that never stops cannot outlast it.` : "",
    },
    {
      ok: ok("Every container removed"),
      title: "Containers destroyed",
      stat: `${report.containment.removed} of ${total} removed`,
      note: "Fresh container per task, none left behind.",
    },
  ];
  return (
    <section aria-label="What was contained" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {tiles.map((t) => (
        <div key={t.title} className={`rounded-lg border p-3 ${t.ok ? "border-pass/40 bg-pass/5" : "border-fail/50 bg-fail/10"}`}>
          <div className={`flex items-center gap-1.5 text-[15px] font-semibold leading-tight ${t.ok ? "text-pass" : "text-fail"}`}>
            <Icon name={t.ok ? "check" : "x"} className="h-4 w-4 shrink-0" /> {t.title}
          </div>
          <div className="mt-1.5 font-mono text-[13px] text-ink">{t.stat}</div>
          <p className="mt-1 text-[11.5px] leading-snug text-muted">{t.note}</p>
        </div>
      ))}
    </section>
  );
}
