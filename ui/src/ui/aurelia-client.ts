// Thin HTTP client for Aurelia backend at http://localhost:8000

const BASE_URL = "http://localhost:8000";

export type AureliaAgent = {
  name: string;
  status: string;
  incarnation: number;
  cycle: number;
  budget_remaining: number;
  weekly_budget: number;
};

export type AureliaMessageResponse = {
  content: string;
  incarnation: number;
  cycle: number;
};

export type AureliaHistoryEntry = {
  role: string;
  content: string;
  timestamp?: string;
};

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<{ status: string; agents?: AureliaAgent[] }> {
  return apiFetch("/health");
}

export async function fetchAgents(): Promise<AureliaAgent[]> {
  try {
    return await apiFetch<AureliaAgent[]>("/agents");
  } catch {
    // Return mock data if endpoint doesn't exist yet
    return [
      { name: "main", status: "idle", incarnation: 1, cycle: 0, budget_remaining: 100, weekly_budget: 100 },
    ];
  }
}

export async function sendMessage(
  agent: string,
  message: string,
): Promise<AureliaMessageResponse> {
  return apiFetch<AureliaMessageResponse>("/message", {
    method: "POST",
    body: JSON.stringify({ agent, message }),
  });
}

export async function fetchHistory(agent: string): Promise<unknown[]> {
  try {
    return await apiFetch<unknown[]>(`/history/${encodeURIComponent(agent)}`);
  } catch {
    return [];
  }
}

export async function fetchTranscript(agent: string, incarnation: number): Promise<AureliaHistoryEntry[]> {
  try {
    return await apiFetch<AureliaHistoryEntry[]>(
      `/history/${encodeURIComponent(agent)}/${incarnation}`,
    );
  } catch {
    return [];
  }
}
