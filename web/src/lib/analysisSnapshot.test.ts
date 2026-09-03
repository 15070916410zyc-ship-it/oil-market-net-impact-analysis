import { describe, expect, it } from "vitest";

import { createExplanationPacket } from "./analysisSnapshot";

describe("AI explanation packet", () => {
  it("accepts verified calculations and rounds displayed numbers to three decimals", () => {
    const packet = createExplanationPacket({
      mode: "verified-live",
      asOf: "2026-08-31",
      method: "VMD + Granger + FEVD",
      sources: [{ id: "GPRD", providerId: "GPRD" }],
      result: { netImpact: 1.23456, pValue: 0.012345, significant: true },
    });
    expect(packet.result).toEqual({ netImpact: 1.235, pValue: 0.012, significant: true });
  });

  it("rejects demo, empty-source and non-finite result payloads", () => {
    expect(() => createExplanationPacket({ mode: "demo", asOf: "2026-08-31", method: "x", sources: [{ id: "x", providerId: "x" }], result: { value: 1 } })).toThrow(/verified/i);
    expect(() => createExplanationPacket({ mode: "verified-live", asOf: "2026-08-31", method: "x", sources: [], result: { value: 1 } })).toThrow(/source/i);
    expect(() => createExplanationPacket({ mode: "verified-live", asOf: "2026-08-31", method: "x", sources: [{ id: "x", providerId: "x" }], result: { value: Number.NaN } })).toThrow(/finite/i);
  });
});
