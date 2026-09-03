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

export const LOCAL_AI_CONTEXT = {
  standard: 4096,
  high: 8192,
} as const;

const DEFAULT_RESULT_CHAR_BUDGET = 2600;

type CompactProfile = {
  maxDepth: number;
  maxArrayItems: number;
  maxObjectEntries: number;
  maxStringLength: number;
};

type CompactState = { shortened: boolean; seen: WeakSet<object> };

function compactValue(value: unknown, profile: CompactProfile, state: CompactState, depth = 0): unknown {
  if (typeof value === "number") return Number.isFinite(value) ? Number(value.toFixed(3)) : null;
  if (typeof value === "string") {
    if (value.length <= profile.maxStringLength) return value;
    state.shortened = true;
    return `${value.slice(0, profile.maxStringLength)}…`;
  }
  if (value === null || typeof value === "boolean" || value === undefined) return value ?? null;
  if (typeof value !== "object") return String(value);
  if (state.seen.has(value)) {
    state.shortened = true;
    return "[circular value omitted]";
  }
  if (depth >= profile.maxDepth) {
    state.shortened = true;
    return Array.isArray(value) ? `[${value.length} nested items omitted]` : "[nested fields omitted]";
  }
  state.seen.add(value);
  if (Array.isArray(value)) {
    const keep = Math.max(2, profile.maxArrayItems);
    if (value.length <= keep) return value.map((item) => compactValue(item, profile, state, depth + 1));
    state.shortened = true;
    const headCount = Math.ceil(keep / 2);
    const tailCount = Math.floor(keep / 2);
    return [
      ...value.slice(0, headCount).map((item) => compactValue(item, profile, state, depth + 1)),
      { omittedItems: value.length - keep },
      ...value.slice(-tailCount).map((item) => compactValue(item, profile, state, depth + 1)),
    ];
  }
  const entries = Object.entries(value as Record<string, unknown>);
  const keptEntries = entries.slice(0, profile.maxObjectEntries);
  if (keptEntries.length < entries.length) state.shortened = true;
  const compacted = Object.fromEntries(
    keptEntries.map(([key, item]) => [key, compactValue(item, profile, state, depth + 1)]),
  );
  if (keptEntries.length < entries.length) compacted.omittedFields = entries.length - keptEntries.length;
  return compacted;
}

export function serializeExplanationResult(result: unknown, maxChars = DEFAULT_RESULT_CHAR_BUDGET) {
  const profiles: CompactProfile[] = [
    { maxDepth: 6, maxArrayItems: 8, maxObjectEntries: 30, maxStringLength: 240 },
    { maxDepth: 5, maxArrayItems: 5, maxObjectEntries: 20, maxStringLength: 160 },
    { maxDepth: 4, maxArrayItems: 3, maxObjectEntries: 14, maxStringLength: 100 },
  ];
  for (const profile of profiles) {
    const state: CompactState = { shortened: false, seen: new WeakSet<object>() };
    const text = JSON.stringify(compactValue(result, profile, state), null, 2);
    if (text.length <= maxChars) return { text, shortened: state.shortened };
  }
  const state: CompactState = { shortened: true, seen: new WeakSet<object>() };
  const text = JSON.stringify(compactValue(result, profiles.at(-1)!, state), null, 0);
  const marker = "\n…[remaining repeated observations omitted]";
  return { text: `${text.slice(0, Math.max(0, maxChars - marker.length))}${marker}`, shortened: true };
}

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

export function buildExplanationPrompt(packet: ExplanationPacket, lang: "zh" | "en", maxResultChars = DEFAULT_RESULT_CHAR_BUDGET) {
  const serialized = serializeExplanationResult(packet.result, maxResultChars);
  const dataNote = serialized.shortened
    ? (lang === "zh" ? "为适配本地模型，重复观测已抽样压缩；不得推断未显示的数值。" : "Repeated observations were sampled to fit the local model; do not infer omitted values.")
    : "";
  if (lang === "zh") {
    return `请只根据下面经过校验的分析结果解释油价研究结论。不得编造数据、来源、因果关系或投资收益；明确区分统计关联与因果关系；所有数值最多保留三位小数。${dataNote}\n方法：${packet.method}\n数据截止：${packet.asOf}\n来源：${packet.sources.join(", ")}\n结果：\n${serialized.text}`;
  }
  return `Explain the oil-price research result using only the verified payload below. Do not invent data, sources, causality, or investment returns. Separate statistical association from causation and show no more than three decimals. ${dataNote}\nMethod: ${packet.method}\nAs of: ${packet.asOf}\nSources: ${packet.sources.join(", ")}\nResult:\n${serialized.text}`;
}
