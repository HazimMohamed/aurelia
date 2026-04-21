import type { IconName } from "./icons.ts";
import rawConfig from "./tool-display.json" with { type: "json" };

// Inlined stubs for tool-display-common functions — not importing from openclaw source

function normalizeToolName(name?: string): string {
  return (name ?? "").trim().toLowerCase();
}

function normalizeVerb(verb?: string): string | undefined {
  if (!verb) return undefined;
  return verb.trim() || undefined;
}

function defaultTitle(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function resolveDetailFromKeys(
  args: unknown,
  keys: string[],
  _opts?: unknown,
): string | undefined {
  if (!args || typeof args !== "object") return undefined;
  const record = args as Record<string, unknown>;
  for (const key of keys) {
    const val = record[key];
    if (val != null && typeof val !== "object") {
      return String(val);
    }
  }
  return undefined;
}

function resolveReadDetail(args: unknown): string | undefined {
  if (!args || typeof args !== "object") return undefined;
  const record = args as Record<string, unknown>;
  return typeof record.path === "string" ? record.path : undefined;
}

function resolveWriteDetail(args: unknown): string | undefined {
  if (!args || typeof args !== "object") return undefined;
  const record = args as Record<string, unknown>;
  return typeof record.path === "string"
    ? record.path
    : typeof record.file_path === "string"
      ? record.file_path
      : undefined;
}

function resolveActionSpec(
  spec: Record<string, unknown> | undefined | null,
  action: string | undefined,
): Record<string, unknown> | undefined {
  if (!spec || !action) return undefined;
  const actions = spec.actions as Record<string, unknown> | undefined;
  if (!actions) return undefined;
  return actions[action] as Record<string, unknown> | undefined;
}

type ToolDisplaySpec = {
  icon?: string;
  title?: string;
  label?: string;
  verb?: string;
  detailKeys?: string[];
  actions?: Record<string, { label?: string; detailKeys?: string[] }>;
};

type ToolDisplayConfig = {
  version?: number;
  fallback?: ToolDisplaySpec;
  tools?: Record<string, ToolDisplaySpec>;
};

export type ToolDisplay = {
  name: string;
  icon: IconName;
  title: string;
  label: string;
  verb?: string;
  detail?: string;
};

const TOOL_DISPLAY_CONFIG = rawConfig as ToolDisplayConfig;
const FALLBACK = TOOL_DISPLAY_CONFIG.fallback ?? { icon: "puzzle" };
const TOOL_MAP = TOOL_DISPLAY_CONFIG.tools ?? {};

function shortenHomeInString(input: string): string {
  if (!input) {
    return input;
  }
  const patterns = [
    { re: /^\/Users\/[^/]+(\/|$)/, replacement: "~$1" },
    { re: /^\/home\/[^/]+(\/|$)/, replacement: "~$1" },
    { re: /^C:\\Users\\[^\\]+(\\|$)/i, replacement: "~$1" },
  ] as const;

  for (const pattern of patterns) {
    if (pattern.re.test(input)) {
      return input.replace(pattern.re, pattern.replacement);
    }
  }

  return input;
}

export function resolveToolDisplay(params: {
  name?: string;
  args?: unknown;
  meta?: string;
}): ToolDisplay {
  const name = normalizeToolName(params.name);
  const key = name.toLowerCase();
  const spec = TOOL_MAP[key];
  const icon = (spec?.icon ?? FALLBACK.icon ?? "puzzle") as IconName;
  const title = spec?.title ?? defaultTitle(name);
  const label = spec?.label ?? name;
  const actionRaw =
    params.args && typeof params.args === "object"
      ? ((params.args as Record<string, unknown>).action as string | undefined)
      : undefined;
  const action = typeof actionRaw === "string" ? actionRaw.trim() : undefined;
  const actionSpec = resolveActionSpec(spec, action);
  const verb = normalizeVerb((actionSpec?.label ?? action) as string | undefined);

  let detail: string | undefined;
  if (key === "read") {
    detail = resolveReadDetail(params.args);
  }
  if (!detail && (key === "write" || key === "edit" || key === "attach")) {
    detail = resolveWriteDetail(params.args);
  }

  const detailKeys = (actionSpec?.detailKeys ?? spec?.detailKeys ?? FALLBACK.detailKeys ?? []) as string[];
  if (!detail && detailKeys.length > 0) {
    detail = resolveDetailFromKeys(params.args, detailKeys);
  }

  if (!detail && params.meta) {
    detail = params.meta;
  }

  if (detail) {
    detail = shortenHomeInString(detail);
  }

  return {
    name,
    icon,
    title,
    label,
    verb,
    detail,
  };
}

export function formatToolDetail(display: ToolDisplay): string | undefined {
  const parts: string[] = [];
  if (display.verb) {
    parts.push(display.verb);
  }
  if (display.detail) {
    parts.push(display.detail);
  }
  if (parts.length === 0) {
    return undefined;
  }
  return parts.join(" · ");
}

export function formatToolSummary(display: ToolDisplay): string {
  const detail = formatToolDetail(display);
  return detail ? `${display.label}: ${detail}` : display.label;
}
