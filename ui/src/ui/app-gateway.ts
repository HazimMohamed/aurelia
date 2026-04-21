// Stub — Aurelia uses HTTP polling, not WebSocket gateway
import type { AppViewState } from "./app-view-state.ts";

export function connectGateway(_host: Partial<AppViewState>) {
  // no-op: Aurelia talks directly to HTTP API
}
