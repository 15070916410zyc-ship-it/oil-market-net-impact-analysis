export type LocalAiLevel = "unsupported" | "standard" | "high";

export type LocalAiCapabilityInput = {
  webGpu: boolean;
  memoryGb?: number;
  mobile: boolean;
};

export type ExplanationPacket = {
  method: string;
  asOf: string;
  sources: string[];
  result: unknown;
};

const STANDARD_MODEL = "Qwen3-1.7B-q4f16_1-MLC";
const HIGH_MODEL = "Qwen3-4B-q4f16_1-MLC";

export function assessLocalAiCapability(input: LocalAiCapabilityInput) {
  if (!input.webGpu || input.mobile || (input.memoryGb !== undefined && input.memoryGb < 6)) {
    return { level: "unsupported" as LocalAiLevel, modelId: null, reason: "webgpu-or-memory" };
  }
  if ((input.memoryGb ?? 8) >= 12) {
    return { level: "high" as LocalAiLevel, modelId: HIGH_MODEL, reason: "capable-desktop" };
  }
  return { level: "standard" as LocalAiLevel, modelId: STANDARD_MODEL, reason: "standard-desktop" };
}

export function detectLocalAiCapability() {
  const browser = navigator as Navigator & { gpu?: unknown; deviceMemory?: number };
  return assessLocalAiCapability({
    webGpu: Boolean(browser.gpu),
    memoryGb: browser.deviceMemory,
    mobile: /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent),
  });
}

export function buildExplanationPrompt(packet: ExplanationPacket, lang: "zh" | "en") {
  const data = JSON.stringify(packet.result, null, 2);
  if (lang === "zh") {
    return `请只根据下面经过校验的分析结果解释油价研究结论。不得编造数据、来源、因果关系或投资收益；明确区分统计关联与因果关系；所有数值最多保留三位小数。\n方法：${packet.method}\n数据截止：${packet.asOf}\n来源：${packet.sources.join(", ")}\n结果：\n${data}`;
  }
  return `Explain the oil-price research result using only the verified payload below. Do not invent data, sources, causality, or investment returns. Separate statistical association from causation and show no more than three decimals.\nMethod: ${packet.method}\nAs of: ${packet.asOf}\nSources: ${packet.sources.join(", ")}\nResult:\n${data}`;
}
