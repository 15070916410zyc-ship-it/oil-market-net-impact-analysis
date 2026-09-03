import { describe, expect, it } from "vitest";

import { assessLocalAiCapability, buildExplanationPrompt } from "./localExplanation";

describe("browser-local explanation", () => {
  it("rejects unsupported devices before a model download is attempted", () => {
    expect(assessLocalAiCapability({ webGpu: false, memoryGb: 32, mobile: false }).level).toBe("unsupported");
    expect(assessLocalAiCapability({ webGpu: true, memoryGb: 4, mobile: false }).level).toBe("unsupported");
  });

  it("selects a smaller model for ordinary devices and Qwen3-4B for capable desktops", () => {
    expect(assessLocalAiCapability({ webGpu: true, memoryGb: 8, mobile: false }).modelId).toContain("1.7B");
    expect(assessLocalAiCapability({ webGpu: true, memoryGb: 16, mobile: false }).modelId).toContain("4B");
  });

  it("grounds explanations in the verified packet and forbids invented data", () => {
    const prompt = buildExplanationPrompt({ method: "VAR/FEVD", asOf: "2026-09-01", sources: ["FRED"], result: { share: 0.321 } }, "en");
    expect(prompt).toContain("VAR/FEVD");
    expect(prompt).toContain("2026-09-01");
    expect(prompt).toContain("Do not invent");
    expect(prompt).toContain("0.321");
  });
});
