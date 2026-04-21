// Polling stubs for Aurelia — only logs polling is active
import { loadLogs } from "./controllers/logs.ts";

type PollingHost = {
  nodesPollInterval: number | null;
  logsPollInterval: number | null;
  debugPollInterval: number | null;
  tab: string;
};

export function startNodesPolling(_host: PollingHost) {
  // no-op: no nodes concept in Aurelia
}

export function stopNodesPolling(_host: PollingHost) {
  // no-op
}

export function startLogsPolling(host: PollingHost) {
  if (host.logsPollInterval != null) {
    return;
  }
  host.logsPollInterval = window.setInterval(() => {
    if (host.tab !== "logs") {
      return;
    }
    void loadLogs(host as unknown as Parameters<typeof loadLogs>[0], { quiet: true });
  }, 2000);
}

export function stopLogsPolling(host: PollingHost) {
  if (host.logsPollInterval == null) {
    return;
  }
  clearInterval(host.logsPollInterval);
  host.logsPollInterval = null;
}

export function startDebugPolling(_host: PollingHost) {
  // no-op
}

export function stopDebugPolling(_host: PollingHost) {
  // no-op
}
