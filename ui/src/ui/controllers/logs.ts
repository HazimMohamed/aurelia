import type { LogEntry, LogLevel } from "../types.ts";

export type LogsState = {
  logsLoading: boolean;
  logsError: string | null;
  logsCursor: number | null;
  logsFile: string | null;
  logsEntries: LogEntry[];
  logsTruncated: boolean;
  logsLastFetchAt: number | null;
  logsLimit: number;
  logsMaxBytes: number;
};

const LOG_BUFFER_LIMIT = 2000;
const LEVELS = new Set<LogLevel>(["trace", "debug", "info", "warn", "error", "fatal"]);

function normalizeLevel(value: unknown): LogLevel | null {
  if (typeof value !== "string") {
    return null;
  }
  const lowered = value.toLowerCase() as LogLevel;
  return LEVELS.has(lowered) ? lowered : null;
}

export function parseLogLine(line: string): LogEntry {
  if (!line.trim()) {
    return { raw: line, message: line };
  }
  try {
    const obj = JSON.parse(line) as Record<string, unknown>;
    const time = typeof obj.time === "string" ? obj.time : null;
    const level = normalizeLevel(obj.level ?? obj.levelname);
    const message =
      typeof obj.message === "string"
        ? obj.message
        : typeof obj.msg === "string"
          ? obj.msg
          : line;
    const subsystem = typeof obj.name === "string" ? obj.name : null;
    return { raw: line, time, level, subsystem, message };
  } catch {
    return { raw: line, message: line };
  }
}

export async function loadLogs(state: LogsState, opts?: { reset?: boolean; quiet?: boolean }) {
  if (state.logsLoading && !opts?.quiet) {
    return;
  }
  if (!opts?.quiet) {
    state.logsLoading = true;
  }
  state.logsError = null;
  try {
    // Fetch from Aurelia backend logs endpoint (may not exist yet — stub with empty)
    const url = new URL("http://localhost:8000/logs");
    if (!opts?.reset && state.logsCursor != null) {
      url.searchParams.set("cursor", String(state.logsCursor));
    }
    url.searchParams.set("limit", String(state.logsLimit));

    let lines: string[] = [];
    let nextCursor: number | null = null;
    let file: string | null = null;

    try {
      const res = await fetch(url.toString());
      if (res.ok) {
        const payload = (await res.json()) as {
          lines?: string[];
          cursor?: number;
          file?: string;
          truncated?: boolean;
        };
        lines = Array.isArray(payload.lines) ? payload.lines.filter((l) => typeof l === "string") : [];
        nextCursor = typeof payload.cursor === "number" ? payload.cursor : null;
        file = typeof payload.file === "string" ? payload.file : null;
        state.logsTruncated = Boolean(payload.truncated);
      }
    } catch {
      // Endpoint not available yet — silently ignore
    }

    const entries = lines.map(parseLogLine);
    const shouldReset = Boolean(opts?.reset || state.logsCursor == null);
    state.logsEntries = shouldReset
      ? entries
      : [...state.logsEntries, ...entries].slice(-LOG_BUFFER_LIMIT);
    if (nextCursor != null) {
      state.logsCursor = nextCursor;
    }
    if (file) {
      state.logsFile = file;
    }
    state.logsLastFetchAt = Date.now();
  } catch (err) {
    state.logsError = String(err);
  } finally {
    if (!opts?.quiet) {
      state.logsLoading = false;
    }
  }
}
