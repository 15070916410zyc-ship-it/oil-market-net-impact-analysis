import { describe, expect, it } from "vitest";

import { assessLocalAiCapability, buildExplanationPrompt, LOCAL_AI_CONTEXT, serializeExplanationResult } from "./localExplanation";

describe("browser-local explanation", () => {
  it("rejects unsupported devices before a model download is attempted", () => {
    expect(assessLocalAiCapability({ webGpu: false, memoryGb: 32, mobile: false }).level).toBe("unsupported");
    expect(assessLocalAiCapability({ webGpu: true, memoryGb: 4, mobile: false }).level).toBe("unsupported");
  });

  it("selects a smaller model for ordinary devices and Qwen3-4B for capable desktops", () => {
    expect(assessLocalAiCapability({ webGpu: true, memoryGb: 8, mobile: false }).modelId).toContain("1.7B");
    expect(assessLocalAiCapability({ webGpu: true, memoryGb: 16, mobile: false }).modelId).toContain("4B");
  });

  it("gives the high-capability model a larger context window", () => {
    expect(LOCAL_AI_CONTEXT.high).toBeGreaterThan(LOCAL_AI_CONTEXT.standard);
    expect(LOCAL_AI_CONTEXT.standard).toBe(4096);
  });

  it("grounds explanations in the verified packet and forbids invented data", () => {
    const prompt = buildExplanationPrompt({ method: "VAR/FEVD", asOf: "2026-09-01", sources: ["FRED"], result: { share: 0.321 } }, "en");
    expect(prompt).toContain("VAR/FEVD");
    expect(prompt).toContain("2026-09-01");
    expect(prompt).toContain("Do not invent");
    expect(prompt).toContain("0.321");
  });

  it("samples long repeated results without exceeding the prompt budget", () => {
    const result = {
      granger: Array.from({ length: 120 }, (_, index) => ({ factor: `factor-${index}`, p: index / 1000, note: "x".repeat(80) })),
      fevd: Array.from({ length: 120 }, (_, index) => ({ horizon: index + 1, share: index / 120 })),
      breakTest: { date: "2020-05-01", statistic: 12.34567 },
    };
    const serialized = serializeExplanationResult(result, 1600);
    const prompt = buildExplanationPrompt({ method: "Granger/FEVD", asOf: "2026-09-01", sources: ["FRED", "EIA"], result }, "zh", 1600);
    expect(serialized.text.length).toBeLessThanOrEqual(1600);
    expect(serialized.shortened).toBe(true);
    expect(prompt).toContain("不得推断未显示的数值");
    expect(prompt).toContain("Granger/FEVD");
    expect(prompt).not.toContain("factor-60");
  });
});
