export type SavedRecord = {
  id: string;
  kind: "series" | "scenario" | "preference";
  label: string;
  payload: Record<string, unknown>;
  savedAt: string;
};

const STORAGE_KEY = "opi.savedRecords.v1";

export function saveLocalRecord(record: Omit<SavedRecord, "savedAt">): SavedRecord {
  const full = { ...record, savedAt: new Date().toISOString() };
  const existing = readLocalRecords().filter((item) => item.id !== full.id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify([full, ...existing]));
  return full;
}

export function readLocalRecords(): SavedRecord[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]") as SavedRecord[];
  } catch {
    return [];
  }
}

export const analysisApiBaseUrl = import.meta.env.VITE_ANALYSIS_API_BASE_URL?.replace(/\/$/, "") || "";
export const isLiveAnalysisApi = Boolean(analysisApiBaseUrl);

export async function requestLiveAnalysis<T>(path: string, body: unknown): Promise<T | null> {
  if (!analysisApiBaseUrl) return null;
  const response = await fetch(`${analysisApiBaseUrl}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Analysis API returned ${response.status}`);
  return response.json() as Promise<T>;
}
