import { create } from "zustand";
import { loadSettings, saveSettings, type UiSettings } from "../lib/storage";
import type { AureliaAgent, AureliaIncarnation } from "../lib/api";
import type { LogEntry, LogLevel } from "../lib/types";

export type Tab = "chat" | "agents" | "logs";
export type ThemeMode = "system" | "light" | "dark";

export type RawMessage = {
  role: string;
  content: unknown[];
  timestamp: number;
};

export type ToolMessage = {
  type: string;
  tool_use_id: string;
  name: unknown;
  input: unknown;
  running: boolean;
  result?: unknown;
};

const DEFAULT_LEVEL_FILTERS: Record<LogLevel, boolean> = {
  trace: false,
  debug: true,
  info: true,
  warn: true,
  error: true,
  fatal: true,
};

type State = {
  // Connection
  connected: boolean;
  lastError: string | null;

  // Settings & navigation
  settings: UiSettings;
  tab: Tab;

  // Agents
  agentsList: AureliaAgent[] | null;
  agentsLoading: boolean;
  agentsError: string | null;
  selectedAgentId: string | null;

  // Incarnations
  incarnationsList: AureliaIncarnation[] | null;
  incarnationsLoading: boolean;
  incarnationsError: string | null;
  selectedIncarnationId: string | null;

  // Chat
  chatMessages: RawMessage[];
  chatToolMessages: ToolMessage[];
  chatStream: string | null;
  chatStreamStartedAt: number | null;
  chatSending: boolean;
  chatLoading: boolean;
  chatDraft: string;
  showThinking: boolean;

  // Logs
  logsEntries: LogEntry[];
  logsLoading: boolean;
  logsError: string | null;
  logsCursor: number | null;
  logsFilterText: string;
  logsLevelFilters: Record<LogLevel, boolean>;
  logsAutoFollow: boolean;

  // Actions
  setConnected: (v: boolean) => void;
  setLastError: (v: string | null) => void;
  setTab: (v: Tab) => void;
  applySettings: (patch: Partial<UiSettings>) => void;
  setAgentsList: (v: AureliaAgent[] | null) => void;
  setAgentsLoading: (v: boolean) => void;
  setAgentsError: (v: string | null) => void;
  setSelectedAgentId: (v: string | null) => void;
  setIncarnationsList: (v: AureliaIncarnation[] | null) => void;
  setIncarnationsLoading: (v: boolean) => void;
  setIncarnationsError: (v: string | null) => void;
  setSelectedIncarnationId: (v: string | null) => void;
  setChatMessages: (v: RawMessage[] | ((prev: RawMessage[]) => RawMessage[])) => void;
  setChatToolMessages: (v: ToolMessage[] | ((prev: ToolMessage[]) => ToolMessage[])) => void;
  setChatStream: (v: string | null) => void;
  setChatStreamStartedAt: (v: number | null) => void;
  setChatSending: (v: boolean) => void;
  setChatLoading: (v: boolean) => void;
  setChatDraft: (v: string) => void;
  toggleShowThinking: () => void;
  setLogsEntries: (v: LogEntry[]) => void;
  appendLogsEntries: (v: LogEntry[]) => void;
  setLogsLoading: (v: boolean) => void;
  setLogsError: (v: string | null) => void;
  setLogsCursor: (v: number | null) => void;
  setLogsFilterText: (v: string) => void;
  toggleLogsLevel: (level: LogLevel) => void;
  setLogsAutoFollow: (v: boolean) => void;
  persistSelection: () => void;
};

const initialSettings = loadSettings();

export const useStore = create<State>((set, get) => ({
  connected: false,
  lastError: null,

  settings: initialSettings,
  tab: "chat",

  agentsList: null,
  agentsLoading: false,
  agentsError: null,
  selectedAgentId: initialSettings.selectedAgent || null,

  incarnationsList: null,
  incarnationsLoading: false,
  incarnationsError: null,
  selectedIncarnationId: initialSettings.selectedIncarnation || null,

  chatMessages: [],
  chatToolMessages: [],
  chatStream: null,
  chatStreamStartedAt: null,
  chatSending: false,
  chatLoading: false,
  chatDraft: "",
  showThinking: initialSettings.chatShowThinking ?? true,

  logsEntries: [],
  logsLoading: false,
  logsError: null,
  logsCursor: null,
  logsFilterText: "",
  logsLevelFilters: { ...DEFAULT_LEVEL_FILTERS },
  logsAutoFollow: true,

  setConnected: (v) => set({ connected: v }),
  setLastError: (v) => set({ lastError: v }),
  setTab: (v) => set({ tab: v }),
  applySettings: (patch) => {
    const next = { ...get().settings, ...patch };
    saveSettings(next);
    set({ settings: next });
  },

  setAgentsList: (v) => set({ agentsList: v }),
  setAgentsLoading: (v) => set({ agentsLoading: v }),
  setAgentsError: (v) => set({ agentsError: v }),
  setSelectedAgentId: (v) => set({ selectedAgentId: v }),

  setIncarnationsList: (v) => set({ incarnationsList: v }),
  setIncarnationsLoading: (v) => set({ incarnationsLoading: v }),
  setIncarnationsError: (v) => set({ incarnationsError: v }),
  setSelectedIncarnationId: (v) => set({ selectedIncarnationId: v }),

  setChatMessages: (v) =>
    set((s) => ({ chatMessages: typeof v === "function" ? v(s.chatMessages) : v })),
  setChatToolMessages: (v) =>
    set((s) => ({ chatToolMessages: typeof v === "function" ? v(s.chatToolMessages) : v })),
  setChatStream: (v) => set({ chatStream: v }),
  setChatStreamStartedAt: (v) => set({ chatStreamStartedAt: v }),
  setChatSending: (v) => set({ chatSending: v }),
  setChatLoading: (v) => set({ chatLoading: v }),
  setChatDraft: (v) => set({ chatDraft: v }),
  toggleShowThinking: () => {
    const next = !get().showThinking;
    set({ showThinking: next });
    get().applySettings({ chatShowThinking: next });
  },

  setLogsEntries: (v) => set({ logsEntries: v }),
  appendLogsEntries: (v) =>
    set((s) => ({ logsEntries: [...s.logsEntries, ...v].slice(-2000) })),
  setLogsLoading: (v) => set({ logsLoading: v }),
  setLogsError: (v) => set({ logsError: v }),
  setLogsCursor: (v) => set({ logsCursor: v }),
  setLogsFilterText: (v) => set({ logsFilterText: v }),
  toggleLogsLevel: (level) =>
    set((s) => ({
      logsLevelFilters: { ...s.logsLevelFilters, [level]: !s.logsLevelFilters[level] },
    })),
  setLogsAutoFollow: (v) => set({ logsAutoFollow: v }),

  persistSelection: () => {
    const { selectedAgentId, selectedIncarnationId, applySettings } = get();
    applySettings({
      selectedAgent: selectedAgentId ?? "",
      selectedIncarnation: selectedIncarnationId ?? "",
    });
  },
}));
