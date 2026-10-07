/**
 * State of an open conversation, driven by `/ws/conversations/{id}` events.
 * Pure functions only, so the streaming logic is unit-tested without a socket.
 */
import type { ApiErrorBody, Conversation, ConversationDetail, Message, ToolCallMeta } from '@/core/types/api';

/** What the agent is doing during a run (`status` events). */
export interface RunStatus {
  state: 'generating' | 'retrying' | 'waiting_resources' | 'running_hooks' | 'delegating' | string;
  attempt?: number;
  retry?: number;
  reason?: string;
  delay?: number;
  needs?: Record<string, number>;
  agent?: string;
  conversation_id?: number;
}

/** Live activity of a sub-agent working on a delegated task. */
export interface LiveDelegation {
  conversationId: number;
  agentId: number | null;
  agent: string | null;
  text: string;
  status: string | null;
  tools: string[];
  done: string | null;
}

export interface ChatState {
  conversation: Conversation | null;
  messages: Message[];
  running: boolean;
  /** Answer and reasoning being generated, not stored yet. */
  stream: { text: string; reasoning: string };
  status: RunStatus | null;
  activeTool: ToolCallMeta | null;
  delegations: Record<number, LiveDelegation>;
  /** Last problem reported by the socket (errors of a run are stored as messages). */
  error: ApiErrorBody | null;
}

export type ServerEvent =
  | { type: 'conversation'; conversation: ConversationDetail }
  | { type: 'message'; message: Message }
  | { type: 'token'; delta: string }
  | { type: 'reasoning'; delta: string }
  | { type: 'tool_start'; call: ToolCallMeta }
  | ({ type: 'status' } & RunStatus)
  | { type: 'delegation'; agent_id: number; conversation_id: number; event: ServerEvent }
  | { type: 'done'; reason: 'completed' | 'stopped' | 'error' }
  | { type: 'error'; error: ApiErrorBody };

export type ChatAction = ServerEvent | { type: 'local/reset' } | { type: 'local/sending' } | { type: 'local/dismiss-error' } | { type: 'local/replace'; conversation: ConversationDetail };

export const initialChatState: ChatState = {
  conversation: null,
  messages: [],
  running: false,
  stream: { text: '', reasoning: '' },
  status: null,
  activeTool: null,
  delegations: {},
  error: null,
};

const EMPTY_STREAM = { text: '', reasoning: '' };

function upsert(messages: Message[], message: Message): Message[] {
  const index = messages.findIndex((item) => item.id === message.id);
  if (index === -1) return [...messages, message];
  const next = [...messages];
  next[index] = message;
  return next;
}

function delegationOf(state: ChatState, conversationId: number): LiveDelegation {
  return (
    state.delegations[conversationId] ?? { conversationId, agentId: null, agent: null, text: '', status: null, tools: [], done: null }
  );
}

function applyDelegated(current: LiveDelegation, event: ServerEvent): LiveDelegation {
  switch (event.type) {
    case 'token':
      return { ...current, text: current.text + event.delta };
    case 'message':
      return event.message.role === 'assistant' || event.message.role === 'tool-calling' ? { ...current, text: '' } : current;
    case 'tool_start':
      return { ...current, tools: [...current.tools, event.call.name] };
    case 'status':
      return { ...current, status: event.state === 'delegating' && event.agent ? `delegating to ${event.agent}` : event.state };
    case 'done':
      return { ...current, done: event.reason, status: null };
    default:
      return current;
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'conversation':
    case 'local/replace': {
      const { messages, ...conversation } = action.conversation;
      return { ...initialChatState, conversation, messages: messages ?? [], running: conversation.running };
    }
    case 'local/reset':
      return initialChatState;
    case 'local/sending':
      return { ...state, running: true, error: null, status: null };
    case 'local/dismiss-error':
      return { ...state, error: null };
    case 'message': {
      const role = action.message.role;
      const answered = role === 'assistant' || role === 'tool-calling';
      return {
        ...state,
        messages: upsert(state.messages, action.message),
        stream: answered ? EMPTY_STREAM : state.stream,
        activeTool: role === 'tool-response' ? null : state.activeTool,
      };
    }
    case 'token':
      return { ...state, running: true, stream: { ...state.stream, text: state.stream.text + action.delta } };
    case 'reasoning':
      return { ...state, running: true, stream: { ...state.stream, reasoning: state.stream.reasoning + action.delta } };
    case 'tool_start':
      return { ...state, running: true, activeTool: action.call };
    case 'status': {
      const { type: _type, ...status } = action;
      const delegations =
        status.state === 'delegating' && status.conversation_id
          ? {
              ...state.delegations,
              [status.conversation_id]: { ...delegationOf(state, status.conversation_id), agent: status.agent ?? null },
            }
          : state.delegations;
      return { ...state, running: true, status, delegations };
    }
    case 'delegation': {
      const current = delegationOf(state, action.conversation_id);
      const next = applyDelegated({ ...current, agentId: action.agent_id }, action.event);
      return { ...state, running: true, delegations: { ...state.delegations, [action.conversation_id]: next } };
    }
    case 'done':
      return { ...state, running: false, stream: EMPTY_STREAM, status: null, activeTool: null, delegations: {} };
    case 'error':
      return { ...state, running: false, status: null, error: action.error };
    default:
      return state;
  }
}

// ------------------------------------------------------------------ blocks
export interface ToolCallView {
  call: ToolCallMeta;
  response: Message | null;
}

/** Messages grouped for display: tool responses are attached to their call. */
export type Block =
  | { kind: 'user' | 'assistant' | 'error' | 'system'; message: Message }
  | { kind: 'tools'; message: Message; calls: ToolCallView[] }
  | { kind: 'tool-response'; message: Message };

export function toolCallsOf(message: Message): ToolCallMeta[] {
  const calls = (message.meta?.tool_calls ?? []) as ToolCallMeta[];
  return Array.isArray(calls) ? calls : [];
}

export function toBlocks(messages: Message[]): Block[] {
  const responses = new Map<string, Message>();
  for (const message of messages) {
    const callId = message.meta?.tool_call_id;
    if (message.role === 'tool-response' && typeof callId === 'string') responses.set(callId, message);
  }
  const attached = new Set<number>();
  const blocks: Block[] = [];
  for (const message of messages) {
    if (message.role === 'tool-calling') {
      const calls = toolCallsOf(message).map((call) => {
        const response = responses.get(call.id) ?? null;
        if (response) attached.add(response.id);
        return { call, response };
      });
      blocks.push({ kind: 'tools', message, calls });
    } else if (message.role === 'tool-response') {
      if (!attached.has(message.id)) blocks.push({ kind: 'tool-response', message });
    } else {
      blocks.push({ kind: message.role, message } as Block);
    }
  }
  return blocks;
}

/** The user message that started the answer containing `messageId` (to regenerate it). */
export function promptBefore(messages: Message[], messageId: number): Message | null {
  const index = messages.findIndex((message) => message.id === messageId);
  for (let i = index - 1; i >= 0; i -= 1) if (messages[i].role === 'user') return messages[i];
  return null;
}

/** One-line description of what the agent is doing. */
export function describeStatus(status: RunStatus | null, toolName: string | null): string {
  if (toolName) return toolName === 'delegate_to_agent' ? 'Waiting for a sub-agent' : `Running ${toolName}`;
  if (!status) return 'Thinking';
  switch (status.state) {
    case 'generating':
      return status.attempt && status.attempt > 1 ? `Generating (attempt ${status.attempt})` : 'Generating';
    case 'retrying':
      return `The model failed${status.reason ? `: ${status.reason}` : ''}. Retrying in ${status.delay ?? 0}s (attempt ${(status.attempt ?? 1) + 1} of ${(status.retry ?? 0) + 1})`;
    case 'waiting_resources':
      return `Waiting for ${Object.keys(status.needs ?? {}).join(', ') || 'resources'} to be free`;
    case 'running_hooks':
      return 'Running hooks';
    case 'delegating':
      return `Delegating to ${status.agent ?? 'a sub-agent'}`;
    default:
      return status.state;
  }
}
