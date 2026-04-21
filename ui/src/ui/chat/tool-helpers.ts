/**
 * Helper functions for tool card rendering.
 */

import { PREVIEW_MAX_CHARS, PREVIEW_MAX_LINES, PREVIEW_WRAP_CHARS } from "./constants.ts";

/**
 * Format tool output content for display in the sidebar.
 * Detects JSON and wraps it in a code block with formatting.
 */
export function formatToolOutputForSidebar(text: string): string {
  const trimmed = text.trim();
  // Try to detect and format JSON
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      return "```json\n" + JSON.stringify(parsed, null, 2) + "\n```";
    } catch {
      // Not valid JSON, return as-is
    }
  }
  return text;
}

/**
 * Get a truncated preview of tool output text.
 * Truncates to first N lines or first N characters, whichever is shorter.
 */
export function getTruncatedPreview(text: string): string {
  const allLines = text.split("\n");
  const previewLines: string[] = [];
  let remainingVisualLines = PREVIEW_MAX_LINES;
  let truncated = false;

  for (const line of allLines) {
    if (remainingVisualLines <= 0) {
      truncated = true;
      break;
    }

    const visualLines = Math.max(1, Math.ceil(line.length / PREVIEW_WRAP_CHARS));
    if (visualLines <= remainingVisualLines) {
      previewLines.push(line);
      remainingVisualLines -= visualLines;
      continue;
    }

    const allowedChars = Math.max(1, remainingVisualLines * PREVIEW_WRAP_CHARS);
    previewLines.push(line.slice(0, allowedChars));
    remainingVisualLines = 0;
    truncated = true;
    break;
  }

  let preview = previewLines.join("\n");
  if (preview.length > PREVIEW_MAX_CHARS) {
    preview = preview.slice(0, PREVIEW_MAX_CHARS);
    truncated = true;
  }

  if (!truncated && previewLines.length < allLines.length) {
    truncated = true;
  }

  return truncated ? `${preview}…` : preview;
}

export function isTruncatedByPreview(text: string): boolean {
  return getTruncatedPreview(text) !== text;
}
