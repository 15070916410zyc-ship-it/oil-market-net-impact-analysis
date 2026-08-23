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

const apiUrl = (path: string) => `${analysisApiBaseUrl}${path}`;

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(apiUrl("/api/health"), { headers: { accept: "application/json" } });
    if (!response.ok) return false;
    const payload = await response.json();
    return payload.ok === true;
  } catch {
    return false;
  }
}

export async function fetchCatalog(): Promise<Array<Record<string, string>>> {
  const response = await fetch(apiUrl("/api/catalog"), { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`Catalog API returned ${response.status}`);
  const payload = await response.json();
  return payload.items;
}

export async function fetchSeries(id: string, frequency: "daily" | "monthly") {
  const params = new URLSearchParams({ id, frequency });
  const response = await fetch(apiUrl(`/api/series?${params}`), { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`Series API returned ${response.status}`);
  return response.json() as Promise<{ updated: string; points: Array<{ date: string; value: number }> }>;
}

export async function requestLiveAnalysis<T>(path: string, body: unknown): Promise<T | null> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Analysis API returned ${response.status}`);
  return response.json() as Promise<T>;
}
