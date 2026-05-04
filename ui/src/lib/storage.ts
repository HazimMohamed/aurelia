const KEY = "openclaw.control.settings.v1";

import type { ThemeMode } from "./theme.ts";

export type UiSettings = {
  gatewayUrl: string;
  token: string;
  sessionId: string;
  lastActiveSessionId: string;
  theme: ThemeMode;
  chatFocusMode: boolean;
  chatShowThinking: boolean;
  splitRatio: number;
  navCollapsed: boolean;
  navGroupsCollapsed: Record<string, boolean>;
  selectedAgent: string;
  selectedIncarnation: string;
};

export function loadSettings(): UiSettings {
  const defaultUrl = (() => {
    const backendPort = import.meta.env.VITE_BACKEND_PORT?.trim();
    if (backendPort) {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      return `${proto}://127.0.0.1:${backendPort}`;
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${location.host}`;
  })();

  const defaults: UiSettings = {
    gatewayUrl: defaultUrl,
    token: import.meta.env.VITE_DEV_TOKEN?.trim() ?? "",
    sessionId: "main",
    lastActiveSessionId: "main",
    theme: "system",
    chatFocusMode: false,
    chatShowThinking: true,
    splitRatio: 0.6,
    navCollapsed: false,
    navGroupsCollapsed: {},
    selectedAgent: "",
    selectedIncarnation: "",
  };

  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<UiSettings>;
    const shouldUseBackendOverride = import.meta.env.VITE_BACKEND_PORT?.trim();
    const devToken = import.meta.env.VITE_DEV_TOKEN?.trim();
    return {
      gatewayUrl: shouldUseBackendOverride
        ? defaults.gatewayUrl
        : typeof parsed.gatewayUrl === "string" && parsed.gatewayUrl.trim()
          ? parsed.gatewayUrl.trim()
          : defaults.gatewayUrl,
      token: devToken ? devToken : typeof parsed.token === "string" ? parsed.token : defaults.token,
      sessionId:
        typeof parsed.sessionId === "string" && parsed.sessionId.trim()
          ? parsed.sessionId.trim()
          : defaults.sessionId,
      lastActiveSessionId:
        typeof parsed.lastActiveSessionId === "string" && parsed.lastActiveSessionId.trim()
          ? parsed.lastActiveSessionId.trim()
          : (typeof parsed.sessionId === "string" && parsed.sessionId.trim()) ||
            defaults.lastActiveSessionId,
      theme:
        parsed.theme === "light" || parsed.theme === "dark" || parsed.theme === "system"
          ? parsed.theme
          : defaults.theme,
      chatFocusMode:
        typeof parsed.chatFocusMode === "boolean" ? parsed.chatFocusMode : defaults.chatFocusMode,
      chatShowThinking:
        typeof parsed.chatShowThinking === "boolean"
          ? parsed.chatShowThinking
          : defaults.chatShowThinking,
      splitRatio:
        typeof parsed.splitRatio === "number" &&
        parsed.splitRatio >= 0.4 &&
        parsed.splitRatio <= 0.7
          ? parsed.splitRatio
          : defaults.splitRatio,
      navCollapsed:
        typeof parsed.navCollapsed === "boolean" ? parsed.navCollapsed : defaults.navCollapsed,
      navGroupsCollapsed:
        typeof parsed.navGroupsCollapsed === "object" && parsed.navGroupsCollapsed !== null
          ? parsed.navGroupsCollapsed
          : defaults.navGroupsCollapsed,
      selectedAgent:
        typeof parsed.selectedAgent === "string" ? parsed.selectedAgent : defaults.selectedAgent,
      selectedIncarnation:
        typeof parsed.selectedIncarnation === "string"
          ? parsed.selectedIncarnation
          : defaults.selectedIncarnation,
    };
  } catch {
    return defaults;
  }
}

export function saveSettings(next: UiSettings) {
  localStorage.setItem(KEY, JSON.stringify(next));
}
