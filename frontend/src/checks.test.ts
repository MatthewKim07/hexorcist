import { describe, expect, it } from "vitest";
import { chipLabel, looksBroken } from "./checks";

describe("chipLabel", () => {
  it("builds a max_toggles label from parameters", () => {
    expect(chipLabel({ type: "max_toggles", max_toggles: 2, window_ms: 5000, pin: "D9" }, [])).toBe("≤ 2 switches / 5 s");
  });

  it("falls back to description when parameters are missing", () => {
    const label = chipLabel({ type: "max_toggles", description: "Fan stays calm", pin: "D9" }, []);
    expect(label).toBe("Fan stays calm");
    expect(looksBroken(label)).toBe(false);
  });

  it("never returns undefined or NaN in the label", () => {
    const label = chipLabel({ type: "max_toggles", max_toggles: undefined, window_ms: undefined }, []);
    expect(label).not.toMatch(/undefined|NaN/i);
    expect(chipLabel({ type: "responsive", max_gap_ms: undefined as unknown as number }, [])).not.toMatch(/undefined|NaN/i);
    expect(chipLabel({ type: "serial_period", period_ms: NaN, pattern: "hb" }, [])).not.toMatch(/undefined|NaN/i);
  });
});
