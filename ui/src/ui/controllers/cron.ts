// Stub — cron not used in Aurelia
import type { CronFormState } from "../ui-types.ts";

export async function loadCronJobs(_state: unknown) {}
export async function loadCronStatus(_state: unknown) {}
export async function loadCronRuns(_state: unknown, _jobId: string) {}
export async function toggleCronJob(_state: unknown, _jobId: string, _enabled: boolean) {}
export async function runCronJob(_state: unknown, _jobId: string) {}
export async function removeCronJob(_state: unknown, _jobId: string) {}
export async function addCronJob(_state: unknown) {}

export function normalizeCronFormState(form: CronFormState): CronFormState {
  return form;
}
