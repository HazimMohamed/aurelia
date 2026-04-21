// Stub — device identity not used in Aurelia
export async function loadOrCreateDeviceIdentity(): Promise<{ deviceId: string; publicKey: string }> {
  return { deviceId: "aurelia", publicKey: "" };
}
export async function signDevicePayload(_payload: unknown): Promise<string> {
  return "";
}
