// Stub — sessions not used in Aurelia HTTP API
export async function loadSessions(_state: unknown) {}
export async function patchSession(_state: unknown, _key: string, _patch: unknown) {}
export async function deleteSession(_state: unknown, _key: string) {}
export async function createSession(_state: unknown): Promise<{ sessionId: string } | null> {
  return null;
}
