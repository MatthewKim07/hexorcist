import { ComponentProps } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PinSpec, Scenario, Trace } from "../api";
import { TipProvider } from "./ui";
import { Replay } from "./Replay";

afterEach(cleanup);

const pins: PinSpec[] = [{ pin: "D9", role: "fan", type: "digital_output", scale: "", active_low: false }];
const scenarios: Scenario[] = [{ id: "s1", name: "Nominal", hypothesis: "Steady", source: "builtin", duration_ms: 1000 }];

const trace: Trace = {
  exit_reason: "completed",
  sim_ms: 1000,
  cycles: 1,
  serial_log: [],
  pin_events: [{ t_ms: 0, pin: "D9", value: 0, dir: "out" }],
  pwm_events: [],
  input_trace: [],
};

function renderReplay(props: Partial<ComponentProps<typeof Replay>> = {}) {
  return render(
    <TipProvider>
      <Replay
        pins={pins}
        scenarios={scenarios}
        scenarioId="s1"
        onScenario={() => {}}
        trace={null}
        error=""
        ready={false}
        side="before"
        onSide={() => {}}
        hasAfter={false}
        violations={[]}
        evidence={null}
        startAt={null}
        {...props}
      />
    </TipProvider>,
  );
}

describe("Replay empty states", () => {
  it("shows a loading skeleton while the trace is loading, not Not run yet", () => {
    renderReplay({ ready: true, loading: true, missing: false });
    expect(screen.getByLabelText("Loading replay")).toBeTruthy();
    expect(screen.queryByText("Not run yet")).toBeNull();
    expect((screen.getByLabelText("Play") as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows Not run yet only when the API confirmed no trace", () => {
    renderReplay({ ready: true, loading: false, missing: true });
    expect(screen.getByText("Not run yet")).toBeTruthy();
    expect(screen.queryByLabelText("Loading replay")).toBeNull();
    expect((screen.getByLabelText("Play") as HTMLButtonElement).disabled).toBe(true);
  });

  it("enables play when a trace is present", () => {
    renderReplay({ ready: true, loading: false, missing: false, trace });
    expect(screen.queryByText("Not run yet")).toBeNull();
    expect(screen.queryByLabelText("Loading replay")).toBeNull();
    expect((screen.getByLabelText("Play") as HTMLButtonElement).disabled).toBe(false);
  });
});
