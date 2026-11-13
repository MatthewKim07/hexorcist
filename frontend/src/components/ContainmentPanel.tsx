import { useState } from "react";
import { ContainmentRecord, Guard, Report } from "../api";
import { Collapsible, Fold, Lamp } from "./ui";

function mb(bytes?: number): string {
  return bytes ? `${Math.round(bytes / 1048576)} MiB` : "?";
}

/** The six containment checks as a row of lamps on the page's one screen. A lamp opens the measured detail behind it. */
export function ContainedRow({ report }: { report: Report }) {
  const [open, setOpen] = useState<string | null>(null);
  const c = report.contained;
  if (!c) {
    return null;
  }
  const ok = (label: string) => c.checks.find((x) => x.label === label)?.ok ?? false;
  const total = report.containment.total;
  const items = [
    { label: "Guard flagged it", ok: ok("Input guard flagged the upload"), detail: `${c.guard.reasons.length} red flags, risk score ${c.guard.score.toFixed(1)}. Blocked before any model saw it.` },
    { label: "LLM never saw it", ok: ok("LLM never contacted"), detail: "0 LLM calls. The prompt injection reached no model." },
    { label: "No network", ok: ok("Network disabled"), detail: `Connect ${c.probe.network}, DNS ${c.probe.dns}. NetworkMode none on all ${total} containers.` },
    { label: "No secrets", ok: ok("No control-plane secrets in any output") && ok("No secrets in the sandbox environment"), detail: `${report.containment.secrets_found} found. The API key and passcode were searched for in all ${total} outputs.` },
    { label: "Timeout kill", ok: ok("Runaway firmware killed by wall clock"), detail: c.runaway.ran ? `SIGKILL at ${c.runaway.duration_s} s, limit ${c.runaway.timeout_s} s.` : "Not run." },
    { label: "Containers removed", ok: ok("Every container removed"), detail: `${report.containment.removed} of ${total} removed. A fresh container per task, none left behind.` },
  ];
  const shown = items.find((i) => i.label === open);
  return (
    <section aria-label="What was contained" className="screen rounded-xl border border-[#0b0f0e] bg-screen text-screen-ink shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]">
      <ul className="grid grid-cols-3 gap-y-2 px-2 py-5 sm:grid-cols-6">
        {items.map((i) => (
          <li key={i.label}>
            <button
              aria-pressed={open === i.label}
              aria-label={`${i.label}: ${i.ok ? "held" : "failed"}`}
              onClick={() => setOpen(open === i.label ? null : i.label)}
              className={`key flex w-full flex-col items-center gap-3 rounded-md px-2 py-3 text-center text-xs !font-normal transition-colors hover:text-screen-ink ${open === i.label ? "bg-screen-raised text-screen-ink" : "text-screen-muted"}`}
            >
              <Lamp tone={i.ok ? "pass" : "fail"} />
              {i.label}
            </button>
          </li>
        ))}
      </ul>
      <Collapsible.Root open={!!shown}>
        <Collapsible.Content className="fold">
          <p aria-live="polite" className="border-t border-screen-line px-5 py-3.5 text-sm text-screen-ink">
            {shown?.detail}
          </p>
        </Collapsible.Content>
      </Collapsible.Root>
    </section>
  );
}

function Row({ label, value, ok = true }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-2.5">
      <dt className="text-muted">{label}</dt>
      <dd className={`num text-sm ${ok ? "text-ink" : "text-fail"}`}>{value}</dd>
    </div>
  );
}

/** Everything behind the Containment tab: what the sandbox enforced, read back from docker inspect. */
export function ContainmentDetails({ records, report, guard }: { records: ContainmentRecord[]; report: Report | null; guard?: Guard | null }) {
  const contained = report?.contained;
  if (!records.length) {
    return <p className="py-8 text-muted">No sandbox records.</p>;
  }
  const limits = records[0].limits ?? {};
  const secrets = records.reduce((n, r) => n + r.secrets_found, 0);
  const killed = records.filter((r) => r.timed_out);
  const removed = records.filter((r) => r.removed).length;
  const allNone = records.every((r) => r.limits?.network === "none");
  const mounts = (limits.binds?.length ?? 0) + (limits.mounts?.length ?? 0);
  const reasons = guard && !guard.allowed ? guard.reasons : [];

  return (
    <div className="space-y-8 py-6">
      <dl className="grid gap-x-12 md:grid-cols-2">
        <div>
          <Row label="Network" value={allNone ? "none" : "NOT none"} ok={allNone} />
          <Row label="Secrets found" value={String(secrets)} ok={secrets === 0} />
          <Row label="Root filesystem" value={limits.read_only_rootfs ? "read-only" : "writable"} ok={!!limits.read_only_rootfs} />
          <Row label="Capabilities" value={limits.cap_drop?.includes("ALL") ? "all dropped" : "kept"} ok={!!limits.cap_drop?.includes("ALL")} />
          <Row label="Host mounts" value={String(mounts)} ok={mounts === 0} />
        </div>
        <div>
          <Row label="Containers removed" value={`${removed} / ${records.length}`} ok={removed === records.length} />
          <Row label="User" value={String(limits.user ?? "?")} />
          <Row label="Memory / CPU / PIDs" value={`${mb(limits.memory_bytes)} / ${(limits.nano_cpus ?? 0) / 1e9} / ${limits.pids_limit ?? "?"}`} />
          <Row label="No new privileges" value={limits.no_new_privileges ? "yes" : "no"} ok={!!limits.no_new_privileges} />
          {killed.map((r) => (
            <Row key={r.container_id} label="Killed at timeout" value={`${r.timeout_s} s`} />
          ))}
        </div>
      </dl>

      {contained && (
        <div className="space-y-4">
          <h3 className="text-sm font-medium">What the attacker got</h3>
          <p>{contained.what_the_attacker_got.note}</p>
          <dl className="grid grid-cols-[minmax(0,150px)_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-xs">
            <dt className="num text-muted">/etc/passwd</dt>
            <dd className="num break-words text-muted">{contained.what_the_attacker_got.etc_passwd_users.join(" ")}</dd>
            <dt className="num text-muted">/proc/self/environ</dt>
            <dd className="num break-words text-muted">{contained.what_the_attacker_got.environ_names.join(" ")} (names only)</dd>
            <dt className="num text-muted">~/.ssh/id_rsa</dt>
            <dd className="num break-words text-muted">{contained.what_the_attacker_got.ssh_key}</dd>
          </dl>
          {contained.runaway.ran && <p className="text-muted">{contained.runaway.note}</p>}
        </div>
      )}

      {reasons.length > 0 && (
        <Fold title={`Guard reasons (${reasons.length})`}>
          <ul className="space-y-1.5 pl-5 text-xs text-muted">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Fold>
      )}

      {contained && (
        <Fold title="Compiler output from the attack" contentClassName="space-y-3">
          <pre className="scroll max-h-48 overflow-auto rounded-md border border-line bg-raised p-3 font-mono text-xs text-muted">{contained.hostile_compile_log}</pre>
          <pre className="scroll max-h-64 overflow-auto rounded-md border border-line bg-raised p-3 font-mono text-xs text-muted">{contained.exfil_compile_log}</pre>
        </Fold>
      )}

      <Fold title={`Sandbox records (${records.length})`}>
          <div className="scroll overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-xs">
              <thead className="text-muted">
                <tr>
                  <th className="py-2 pr-4 font-normal">Task</th>
                  <th className="py-2 pr-4 font-normal">Container</th>
                  <th className="py-2 pr-4 text-right font-normal">Time</th>
                  <th className="py-2 pr-4 text-right font-normal">Exit</th>
                  <th className="py-2 font-normal">Events</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => (
                  <tr key={`${r.container_id}-${i}`} className="border-t border-line">
                    <td className="py-2 pr-4">{r.label}</td>
                    <td className="num py-2 pr-4 text-muted">{r.container_id}</td>
                    <td className="num py-2 pr-4 text-right">{(r.duration_ms / 1000).toFixed(1)} s</td>
                    <td className="num py-2 pr-4 text-right">{r.exit_code ?? "?"}</td>
                    <td className="py-2 text-muted">
                      {[r.timed_out && "timeout kill", r.oom_killed && "OOM kill", ...r.violations.filter((v) => v.type !== "timeout_kill" && v.type !== "oom_kill").map((v) => v.type)].filter(Boolean).join(", ") || "none"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      </Fold>
    </div>
  );
}
