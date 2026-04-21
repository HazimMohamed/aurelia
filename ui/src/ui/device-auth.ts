// Stub — device auth not used in Aurelia

export type DeviceAuthEntry = {
  token: string;
  role: string;
  scopes: string[];
  updatedAtMs: number;
};

export function loadDeviceAuthToken(_params: { deviceId: string; role: string }): DeviceAuthEntry | null {
  return null;
}

export function storeDeviceAuthToken(_params: {
  deviceId: string;
  role: string;
  token: string;
  scopes?: string[];
}): DeviceAuthEntry {
  return { token: "", role: "", scopes: [], updatedAtMs: Date.now() };
}

export function clearDeviceAuthToken(_params: { deviceId: string; role: string }) {}
