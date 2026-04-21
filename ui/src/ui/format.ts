// Inlined stubs for format utilities — no longer importing from openclaw source

export function formatRelativeTimestamp(ms: number | null | undefined): string {
  if (ms == null) return "never";
  const diff = Date.now() - ms;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatDurationHuman(ms: number | null | undefined): string {
  if (ms == null || ms < 0) return "-";
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function formatDurationCompact(ms: number | null | undefined): string {
  return formatDurationHuman(ms);
}

export function formatMs(ms?: number | null): string {
  if (!ms && ms !== 0) {
    return "n/a";
  }
  return new Date(ms).toLocaleString();
}

export function formatList(values?: Array<string | null | undefined>): string {
  if (!values || values.length === 0) {
    return "none";
  }
  return values.filter((v): v is string => Boolean(v && v.trim())).join(", ");
}

export function clampText(value: string, max = 120): string {
  if (value.length <= max) {
    return value;
  }
  return `${value.slice(0, Math.max(0, max - 1))}…`;
}

export function truncateText(
  value: string,
  max: number,
): {
  text: string;
  truncated: boolean;
  total: number;
} {
  if (value.length <= max) {
    return { text: value, truncated: false, total: value.length };
  }
  return {
    text: value.slice(0, Math.max(0, max)),
    truncated: true,
    total: value.length,
  };
}

export function toNumber(value: string, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export function parseList(input: string): string[] {
  return input
    .split(/[,\n]/)
    .map((v) => v.trim())
    .filter((v) => v.length > 0);
}

export function stripThinkingTags(value: string): string {
  // Remove <thinking>...</thinking> tags
  return value.replace(/<thinking>[\s\S]*?<\/thinking>/g, "").trim();
}
