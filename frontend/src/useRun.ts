import { useEffect, useReducer } from "react";
import { api, AssertionDef, Bug, ContainmentRecord, Guard, PinSpec, Report, RunDetail, Scenario } from "./api";

export const STEP_ORDER = ["write", "understand", "compile", "attack", "execute", "diagnose", "fix", "verify", "report"] as const;
export type StepName = (typeof STEP_ORDER)[number];

export interface StepState {
  status: "pending" | "running" | "done" | "failed" | "skipped";
  detail: string;
  startedAt?: number;
  endedAt?: number;
}

export interface ScenarioResult {
  iteration: number;
  scenario_id: string;
  name: string;
  passed: boolean;
  failed: string[];
  exit_reason: string;
  duration_ms: number;
}

export interface RunState {
  seq: number;
  guard: Guard | null;
  steps: Partial<Record<StepName, StepState>>;
  deviceModel: Report["device_model"];
  assertions: AssertionDef[];
  scenarios: Scenario[];
  results: Record<number, Record<string, ScenarioResult>>;
  bugs: Bug[];
  records: ContainmentRecord[];
  warnings: string[];
  firmware: string | null;
  spec: { pins: PinSpec[]; behaviour: string } | null;
  doneStatus: string | null;
  run: RunDetail | null;
  connectionLost: boolean;
}

const initial: RunState = {
  seq: 0,
  guard: null,
  steps: {},
  deviceModel: null,
  assertions: [],
  scenarios: [],
  results: {},
  bugs: [],
  records: [],
  warnings: [],
  firmware: null,
  spec: null,
  doneStatus: null,
  run: null,
  connectionLost: false,
};

type Action = { kind: "event"; event: any } | { kind: "run"; run: RunDetail } | { kind: "lost" } | { kind: "reset" };

function reducer(state: RunState, action: Action): RunState {
  if (action.kind === "reset") {
    return initial;
  }
  if (action.kind === "run") {
    return { ...state, run: action.run };
  }
  if (action.kind === "lost") {
    return { ...state, connectionLost: true };
  }
  const e = action.event;
  // EventSource resends on reconnect, and StrictMode can double-subscribe in development.
  if (e.seq <= state.seq) {
    return state;
  }
  const next: RunState = { ...state, seq: e.seq, connectionLost: false };
  switch (e.type) {
    case "guard":
      next.guard = e.guard;
      break;
    case "step": {
      const prev = state.steps[e.step as StepName];
      next.steps = {
        ...state.steps,
        [e.step]: {
          status: e.status,
          detail: e.detail,
          startedAt: prev?.startedAt ?? e.t,
          endedAt: e.status === "running" ? undefined : e.t,
        },
      };
      break;
    }
    case "device_model":
      next.deviceModel = e.device_model;
      break;
    case "assertions":
      next.assertions = e.assertions;
      break;
    case "scenarios":
      next.scenarios = e.scenarios;
      break;
    case "scenario_result":
      next.results = { ...state.results, [e.iteration]: { ...(state.results[e.iteration] ?? {}), [e.scenario_id]: e } };
      break;
    case "bug":
      next.bugs = [...state.bugs, e.bug];
      break;
    case "containment":
      next.records = [...state.records, e.record];
      break;
    case "warning":
      next.warnings = [...state.warnings, e.detail];
      break;
    case "firmware":
      next.firmware = e.firmware;
      break;
    case "spec":
      next.spec = e.spec;
      break;
    case "done":
      next.doneStatus = e.status;
      break;
  }
  return next;
}

export function useRun(runId: string): RunState {
  const [state, dispatch] = useReducer(reducer, initial);

  useEffect(() => {
    dispatch({ kind: "reset" });
    let closed = false;
    const load = () =>
      api
        .run(runId)
        .then((run) => {
          if (!closed) {
            dispatch({ kind: "run", run });
          }
        })
        .catch(() => undefined);
    load();

    const source = new EventSource(`/api/runs/${runId}/events`);
    const onEvent = (msg: MessageEvent) => dispatch({ kind: "event", event: JSON.parse(msg.data) });
    for (const name of ["guard", "step", "device_model", "assertions", "scenarios", "scenario_result", "compile_log", "bug", "iteration", "containment", "warning", "spec", "firmware"]) {
      source.addEventListener(name, onEvent);
    }
    source.addEventListener("done", (msg) => {
      onEvent(msg as MessageEvent);
      load();
    });
    source.addEventListener("end", () => {
      source.close();
      load();
    });
    source.onerror = () => {
      if (source.readyState !== EventSource.CLOSED) {
        dispatch({ kind: "lost" });
      }
    };
    return () => {
      closed = true;
      source.close();
    };
  }, [runId]);

  return state;
}
