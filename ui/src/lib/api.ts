const BASE_URL = "http://localhost:8000";

export type AureliaAgent = {
  name: string;
  status: string;
  incarnation: string | null;
  cycle: number | null;
  last_active: string | null;
  budget_remaining: number;
  weekly_budget: number;
  scheduler_queue: number;
};

export type AureliaIncarnation = {
  name: string;
  status: "active" | "sleeping" | "dissolved";
  cycle: number;
  last_active: string | null;
};

export type TranscriptEntry = {
  ts: string;
  type: string;
  content: string | null;
  cycle: number | null;
  [key: string]: unknown;
};

export type SSEEvent = {
  event: string;
  data: Record<string, unknown>;
};

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<{ status: string }> {
  return apiFetch("/health");
}

export async function fetchAgents(): Promise<AureliaAgent[]> {
  const res = await apiFetch<{ agents: AureliaAgent[] }>("/agents");
  return res.agents;
}

export async function fetchIncarnations(agent: string): Promise<AureliaIncarnation[]> {
  const res = await apiFetch<{ agent: string; incarnations: AureliaIncarnation[] }>(
    `/history/${encodeURIComponent(agent)}`,
  );
  return res.incarnations.filter((i) => i.status !== "dissolved");
}

export async function spawnIncarnation(agent: string): Promise<{ incarnation: string }> {
  return apiFetch(`/agents/${encodeURIComponent(agent)}/spawn`, { method: "POST" });
}

export async function fetchTranscript(
  agent: string,
  incarnationId: string,
): Promise<{ entries: TranscriptEntry[] }> {
  return apiFetch(`/history/${encodeURIComponent(agent)}/${encodeURIComponent(incarnationId)}`);
}

export async function* streamMessage(
  agent: string,
  message: string,
  incarnationId?: string | null,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const to: Record<string, string> = { agent };
  if (incarnationId) to["incarnation_id"] = incarnationId;
  const res = await fetch(`${BASE_URL}/message/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to, content: message }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    const blocks = buf.split("\n\n");
    buf = blocks.pop() ?? "";

    for (const block of blocks) {
      if (!block.trim()) continue;
      let eventName = "message";
      let dataStr = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) eventName = line.slice(7).trim();
        else if (line.startsWith("data: ")) dataStr = line.slice(6).trim();
      }
      if (!dataStr) continue;
      try {
        yield { event: eventName, data: JSON.parse(dataStr) as Record<string, unknown> };
      } catch {
        // skip malformed frames
      }
    }
  }
}
