export type ExplanationPacket = {
  mode: "verified-live";
  asOf: string;
  method: string;
  sources: Array<{ id: string; providerId: string }>;
  result: Record<string, unknown>;
};

function sanitize(value: unknown, path = "result"): unknown {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${path} must contain finite numbers.`);
    return Math.round(value * 1000) / 1000;
  }
  if (Array.isArray(value)) return value.map((item, index) => sanitize(item, `${path}[${index}]`));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, sanitize(item, `${path}.${key}`)]));
  }
  return value;
}

export function createExplanationPacket(input: {
  mode: string;
  asOf: string;
  method: string;
  sources: Array<{ id: string; providerId: string }>;
  result: Record<string, unknown>;
}): ExplanationPacket {
  if (input.mode !== "verified-live") throw new Error("AI explanations require verified live calculations.");
  if (!input.sources.length) throw new Error("AI explanations require at least one verified source.");
  if (!input.asOf || !input.method) throw new Error("AI explanations require an as-of date and method.");
  return {
    mode: "verified-live",
    asOf: input.asOf,
    method: input.method,
    sources: input.sources.map((source) => ({ id: source.id, providerId: source.providerId })),
    result: sanitize(input.result) as Record<string, unknown>,
  };
}
