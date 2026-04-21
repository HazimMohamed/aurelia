// Stub — skills not used in Aurelia
export type SkillMessage = { kind: "error" | "ok"; text: string };

export async function loadSkills(_state: unknown, _opts?: unknown) {}
export async function updateSkillEnabled(_state: unknown, _key: string, _enabled: boolean) {}
export async function updateSkillEdit(_state: unknown, _key: string, _value: string) {}
export async function saveSkillApiKey(_state: unknown, _key: string) {}
export async function installSkill(_state: unknown, _skillKey: string, _name: string, _installId: string) {}
