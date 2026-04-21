// Stub gateway types - Aurelia uses HTTP polling, not WebSocket
// These types are kept for interface compatibility

export type GatewayEventFrame = {
  type: "event";
  event: string;
  payload?: unknown;
  seq?: number;
};

export type GatewayResponseFrame = {
  type: "res";
  id: string;
  ok: boolean;
  payload?: unknown;
  error?: { code: string; message: string; details?: unknown };
};

export type GatewayHelloOk = {
  type: "hello-ok";
  protocol: number;
  features?: { methods?: string[]; events?: string[] };
  snapshot?: unknown;
};

export class GatewayBrowserClient {
  // Stub — Aurelia does not use WebSocket gateway
  request<T = unknown>(_method: string, _params?: unknown): Promise<T> {
    return Promise.reject(new Error("GatewayBrowserClient not used in Aurelia"));
  }

  close() {
    // no-op
  }
}
