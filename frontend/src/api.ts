export type PinType = "analog_input" | "digital_input" | "digital_output" | "pwm_output";

export interface PinSpec {
  pin: string;
  role: string;
  type: PinType;
  scale: string;
  active_low: boolean;
}

/** A machine-checkable assertion with its parameters, as the backend validates and evaluates it. */
export interface Check {
  id?: string;
  type: string;
  description?: string;
  [param: string]: any;
}

export type DeviceModel = { summary: string; inputs: string[]; outputs: string[]; thresholds: string[]; risks: string[] };

/** Checks a run evaluates as given instead of reading the spec again. */
export interface CheckSet {
  assertions: Check[];
  device_model?: DeviceModel | null;
  source: "preview" | "example";
}

export interface CheckPreview {
  assertions: Check[];
  device_model: DeviceModel;
  warnings: string[];
  model: string;
  duration_ms: number;
}

export interface Preset {
  id: string;
  title: string;
  summary: string;
  firmware: string;
  pins: PinSpec[];
  behaviour: string;
  checks?: CheckSet;
}

export interface Health {
  ok: boolean;
  sandbox: { docker: boolean; image: boolean; error: string };
  llm_configured: boolean;
  llm_model: string;
  llm_base_url: string;
  passcode_required: boolean;
}

export interface Guard {
  allowed: boolean;
  score: number;
  reasons: string[];
}

export interface Scenario {
  id: string;
  name: string;
  hypothesis: string;
  source: "builtin" | "llm";
  duration_ms?: number;
  digital?: { pin: string; initial: number }[];
  floating?: { pin: string; from_ms: number; to_ms: number }[];
}

export interface AssertionDef extends Check {
  id: string;
  description: string;
}

export interface Violation {
  t_start: number;
  t_end: number;
  detail: string;
}

export interface AssertionResult {
  assertion_id: string;
  scenario_id: string;
  type: string;
  status: "pass" | "fail" | "not_exercised";
  evidence: string;
  metrics: Record<string, unknown>;
  violations: Violation[];
}

export interface Trace {
  exit_reason: string;
  sim_ms: number;
  cycles: number;
  serial_log: { t_ms: number; text: string }[];
  pin_events: { t_ms: number; pin: string; value: number; dir: "in" | "out" }[];
  pwm_events: { t_ms: number; pin: string; duty: number }[];
  input_trace: { t_ms: number; pin: string; mv: number; min_mv: number; max_mv: number }[];
  pin_events_trimmed_from?: number;
}

export interface ContainmentRecord {
  kind: string;
  label: string;
  container_id: string;
  limits: Record<string, any>;
  duration_ms: number;
  exit_code: number | null;
  oom_killed: boolean;
  timed_out: boolean;
  timeout_s: number;
  removed: boolean;
  env_names: string[];
  secrets_found: number;
  violations: { type: string; detail: string }[];
}

export interface Bug {
  id: string;
  assertion_id: string;
  assertion_type: string;
  requirement: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  root_cause: string;
  code_lines: number[];
  scenario_id: string;
  scenario_name: string;
  evidence: string;
  failing_scenarios: { id: string; name: string; evidence: string }[];
  before?: { status: string; evidence: string } | null;
  after?: { status: string; evidence: string } | null;
  verified?: boolean;
}

export interface Report {
  status: string;
  firmware: string;
  spec: { pins: PinSpec[]; behaviour: string };
  device_model: DeviceModel | null;
  assertions: AssertionDef[];
  scenarios: Scenario[];
  matrix: Record<string, Record<string, AssertionResult[]>>;
  iterations: { n: number; compile_ok: boolean; summary: string; failing: number | null; still_failing: string[]; regressions: string[]; rejected?: boolean }[];
  bugs: Bug[];
  compile_log: string;
  error: string;
  warnings: string[];
  containment: { records: ContainmentRecord[]; total: number; removed: number; secrets_found: number; timeouts: number; oom_kills: number; network_none: boolean | null; violations: number };
  llm: { model: string; calls: number; repairs: number; prompt_tokens: number; completion_tokens: number };
  score: { bugs_found: number; bugs_verified: number; scenarios: number; assertions: number; fix_attempts: number; checks_passed?: number; checks_total?: number };
  fix?: { iteration: number; summary: string; patched_firmware: string; diff: { unified: string; added: number; removed: number }; all_passing: boolean; regressions: string[] };
  contained?: {
    contained: boolean;
    guard: Guard;
    checks: { label: string; ok: boolean; detail: string }[];
    probe: Record<string, any>;
    runaway: { ran: boolean; killed?: boolean; duration_s?: number; timeout_s?: number; note?: string };
    file_reads: string[];
    hostile_compile_log: string;
    exfil_compile_log: string;
    what_the_attacker_got: { etc_passwd_users: string[]; environ_names: string[]; ssh_key: string; note: string };
  };
  build?: { description: string; title: string; attempts: { attempt: number; ok: boolean; error: string }[] };
  spec_checked?: boolean;
  unexercised?: string[];
}

export interface RunSummary {
  id: string;
  created_at: number;
  finished_at: number | null;
  mode: string;
  title: string;
  status: string;
  score: Report["score"] | null;
}

export interface RunDetail extends RunSummary {
  firmware: string;
  spec: { pins: PinSpec[]; behaviour: string };
  guard: Guard;
  report: Report | null;
}

export interface ReviewConcern {
  title: string;
  detail: string;
  lines: number[];
  confidence: "low" | "medium" | "high";
}

export interface Review {
  model: string;
  verdict: "issues_found" | "looks_correct";
  summary: string;
  concerns: ReviewConcern[];
  suggested_fix: string;
  executed: false;
  duration_ms: number;
  tokens: number;
}

export interface ReviewState {
  review: Review | null;
  pending: boolean;
  error: string;
}

const PASSCODE_KEY = "hexorcist.passcode";

export function getPasscode(): string {
  try {
    return localStorage.getItem(PASSCODE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setPasscode(value: string): void {
  try {
    localStorage.setItem(PASSCODE_KEY, value);
  } catch {
    // Private windows can refuse storage. The field still works for this page load.
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${res.status} ${await res.text()}`);
  }
  return res.json();
}

/** True when the server rejected the request for a missing or wrong demo passcode. */
export function isPasscodeError(e: unknown): boolean {
  return e instanceof Error && /passcode/i.test(e.message);
}

async function postJson<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-Passcode": getPasscode() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const parsed = await res.json();
      detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      // Keep the status code as the message.
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  health: () => getJson<Health>("/api/health"),
  presets: () => getJson<Preset[]>("/api/presets"),
  runs: () => getJson<RunSummary[]>("/api/runs"),
  run: (id: string) => getJson<RunDetail>(`/api/runs/${id}`),
  events: (id: string, after: number) => getJson<{ events: any[]; done: boolean }>(`/api/runs/${id}/events.json?after=${after}`),
  trace: (id: string, iteration: number, scenario: string) => getJson<Trace>(`/api/runs/${id}/traces/${iteration}/${scenario}`),
  review: (id: string) => getJson<ReviewState>(`/api/runs/${id}/review`),
  requestReview: (id: string) => postJson<ReviewState>(`/api/runs/${id}/review`),
  start: (body: Record<string, unknown>) => postJson<{ run_id: string; guard: Guard }>("/api/runs", body),
  previewChecks: (body: { firmware: string; pins: PinSpec[]; behaviour: string }) => postJson<CheckPreview>("/api/checks", body),
};
