// Stub — exec approval not used in Aurelia
export type ExecApprovalRequest = {
  id: string;
  command: string;
  cwd?: string | null;
};

export async function addExecApproval(_state: unknown, _req: ExecApprovalRequest) {}
export async function removeExecApproval(_state: unknown, _id: string) {}
export function parseExecApprovalRequested(_payload: unknown): ExecApprovalRequest | null { return null; }
export function parseExecApprovalResolved(_payload: unknown): string | null { return null; }
