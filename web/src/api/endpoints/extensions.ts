import { request } from '../client';
import type {
  AgentPresetData,
  CallableItem,
  ExtensionPreset,
  Instruction,
  InstructionKind,
  ModuleSettings,
  SessionPresetData,
  Skill,
} from '@/core/types/api';

const json = (body: unknown) => JSON.stringify(body);
/** `{extension}/{name}` ids are used as path segments. */
const itemPath = (id: string) => id.split('/').map(encodeURIComponent).join('/');

/** Tools and hooks share the same API shape. */
export function callableApi(kind: 'tools' | 'hooks') {
  return {
    list: () => request<CallableItem[]>(`/${kind}/`),
    reload: () => request<CallableItem[]>(`/${kind}/reload`, { method: 'POST' }),
    settings: () => request<ModuleSettings[]>(`/${kind}/settings`),
    settingsOf: (filePath: string) => request<ModuleSettings>(`/${kind}/settings/${filePath}`),
    saveSettings: (filePath: string, kwargs: Record<string, unknown>) =>
      request<ModuleSettings>(`/${kind}/settings/${filePath}`, { method: 'PUT', body: json({ kwargs }) }),
  };
}

export const tools = callableApi('tools');
export const hooks = callableApi('hooks');

export const instructions = {
  list: (kind: InstructionKind) => request<Instruction[]>(`/instructions/${kind}/`),
  get: (kind: InstructionKind, id: string) => request<Instruction>(`/instructions/${kind}/${itemPath(id)}`),
  create: (kind: InstructionKind, name: string, content: string) =>
    request<Instruction>(`/instructions/${kind}/`, { method: 'POST', body: json({ name, content }) }),
  update: (kind: InstructionKind, id: string, content: string) =>
    request<Instruction>(`/instructions/${kind}/${itemPath(id)}`, { method: 'PUT', body: json({ content }) }),
  remove: (kind: InstructionKind, id: string) => request<void>(`/instructions/${kind}/${itemPath(id)}`, { method: 'DELETE' }),
};

export const skills = {
  list: () => request<Skill[]>('/skills/'),
  get: (id: string) => request<Skill>(`/skills/${itemPath(id)}`),
  create: (name: string, description: string, content: string) =>
    request<Skill>('/skills/', { method: 'POST', body: json({ name, description, content }) }),
  update: (id: string, description: string, content: string) =>
    request<Skill>(`/skills/${itemPath(id)}`, { method: 'PUT', body: json({ description, content }) }),
  remove: (id: string) => request<void>(`/skills/${itemPath(id)}`, { method: 'DELETE' }),
  file: (id: string, path: string) => request<string>(`/skills/${itemPath(id)}/files/${path}`),
};

function presetApi<T extends { name: string }>(base: string) {
  return {
    list: () => request<ExtensionPreset<T>[]>(`/${base}/`),
    get: (id: string) => request<ExtensionPreset<T>>(`/${base}/${itemPath(id)}`),
    create: (data: T) => request<ExtensionPreset<T>>(`/${base}/`, { method: 'POST', body: json(data) }),
    update: (id: string, data: T) => request<ExtensionPreset<T>>(`/${base}/${itemPath(id)}`, { method: 'PUT', body: json(data) }),
    remove: (id: string) => request<void>(`/${base}/${itemPath(id)}`, { method: 'DELETE' }),
  };
}

export const agentPresets = presetApi<AgentPresetData>('agent-presets');
export const sessionPresets = presetApi<SessionPresetData>('session-presets');
