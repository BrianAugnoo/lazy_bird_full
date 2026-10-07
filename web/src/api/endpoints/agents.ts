import { request } from '../client';
import type {
  Agent,
  AgentFields,
  AgentTool,
  Conversation,
  ConversationDetail,
  Message,
  RunOut,
  Session,
} from '@/core/types/api';

const json = (body: unknown) => JSON.stringify(body);

export const sessions = {
  list: () => request<Session[]>('/sessions/'),
  get: (id: number) => request<Session>(`/sessions/${id}`),
  create: (title: string, meta?: Record<string, unknown>) => request<Session>('/sessions/', { method: 'POST', body: json({ title, meta }) }),
  /** Create the session and its agents from a session preset (`{extension}/{name}`). */
  fromPreset: (presetId: string, title?: string) =>
    request<Session>('/sessions/from-preset', { method: 'POST', body: json({ preset_id: presetId, title: title || null }) }),
  update: (id: number, changes: { title?: string; meta?: Record<string, unknown> | null }) =>
    request<Session>(`/sessions/${id}`, { method: 'PATCH', body: json(changes) }),
  remove: (id: number) => request<void>(`/sessions/${id}`, { method: 'DELETE' }),
  /** Talk to the session's master agent; starts a conversation when none is given. */
  chat: (id: number, content: string, conversationId?: number) =>
    request<ConversationDetail>(`/sessions/${id}/chat`, { method: 'POST', body: json({ content, conversation_id: conversationId ?? null }) }),
};

export const agents = {
  list: () => request<Agent[]>('/agents/'),
  ofSession: (sessionId: number) => request<Agent[]>(`/agents/session/${sessionId}`),
  get: (id: number) => request<Agent>(`/agents/${id}`),
  create: (sessionId: number, fields: Partial<AgentFields> & { name: string }) =>
    request<Agent>('/agents/', { method: 'POST', body: json({ ...fields, session_id: sessionId }) }),
  /** Create an agent (and the sub-agents it needs) from an agent preset. */
  fromPreset: (sessionId: number, presetId: string) =>
    request<Agent>('/agents/from-preset', { method: 'POST', body: json({ session_id: sessionId, preset_id: presetId }) }),
  update: (id: number, changes: Partial<AgentFields>) => request<Agent>(`/agents/${id}`, { method: 'PATCH', body: json(changes) }),
  remove: (id: number) => request<void>(`/agents/${id}`, { method: 'DELETE' }),
  /** The tools the agent sees, with the names the LLM gets. */
  tools: (id: number) => request<AgentTool[]>(`/agents/${id}/tools`),
};

export const conversations = {
  list: (agentId?: number) => request<Conversation[]>(`/conversations/${agentId ? `?agent_id=${agentId}` : ''}`),
  get: (id: number) => request<ConversationDetail>(`/conversations/${id}`),
  create: (agentId: number, title?: string) =>
    request<ConversationDetail>('/conversations/', { method: 'POST', body: json({ agent_id: agentId, title: title || null }) }),
  rename: (id: number, title: string) => request<Conversation>(`/conversations/${id}`, { method: 'PATCH', body: json({ title }) }),
  remove: (id: number) => request<void>(`/conversations/${id}`, { method: 'DELETE' }),
  messages: (id: number) => request<Message[]>(`/conversations/${id}/messages`),
  addMessage: (id: number, content: string) => request<Message>(`/conversations/${id}/messages`, { method: 'POST', body: json({ content }) }),
  /** Answer without streaming (the chat page streams over the WebSocket instead). */
  run: (id: number, options?: { retry?: number; max_iter?: number }) =>
    request<RunOut>(`/conversations/${id}/run`, { method: 'POST', body: json(options ?? null) }),
  stop: (id: number) => request<{ stopped: boolean }>(`/conversations/${id}/stop`, { method: 'POST' }),
  /** Delete the messages after `messageId` (to regenerate or edit). */
  rewind: (id: number, messageId: number) =>
    request<ConversationDetail>(`/conversations/${id}/rewind`, { method: 'POST', body: json({ message_id: messageId }) }),
};

export const messages = {
  get: (id: number) => request<Message>(`/messages/${id}`),
  edit: (id: number, content: string) => request<Message>(`/messages/${id}`, { method: 'PATCH', body: json({ content }) }),
  remove: (id: number) => request<void>(`/messages/${id}`, { method: 'DELETE' }),
};
