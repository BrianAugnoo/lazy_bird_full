import { describe, expect, it } from 'vitest';
import type { ConversationDetail, Message } from '@/core/types/api';
import { chatReducer, describeStatus, initialChatState, promptBefore, toBlocks, type ChatState } from './state';

const message = (id: number, role: Message['role'], content: string | null, meta: Message['meta'] = null): Message => ({
  id,
  conversation_id: 1,
  role,
  content,
  meta,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
});

const detail = (messages: Message[], running = false): ConversationDetail => ({
  id: 1,
  agent_id: 1,
  title: 'Chat',
  created_at: '',
  updated_at: '',
  runnable: false,
  running,
  messages,
});

const run = (events: Parameters<typeof chatReducer>[1][], start: ChatState = initialChatState) => events.reduce(chatReducer, start);

describe('chatReducer', () => {
  it('loads the conversation sent on connection', () => {
    const state = run([{ type: 'conversation', conversation: detail([message(1, 'user', 'hi')], true) }]);
    expect(state.messages).toHaveLength(1);
    expect(state.running).toBe(true);
    expect(state.conversation?.title).toBe('Chat');
  });

  it('streams tokens until the answer is stored', () => {
    const streaming = run([
      { type: 'local/sending' },
      { type: 'reasoning', delta: 'Let me ' },
      { type: 'token', delta: 'Hel' },
      { type: 'token', delta: 'lo' },
    ]);
    expect(streaming.stream).toEqual({ text: 'Hello', reasoning: 'Let me ' });
    expect(streaming.running).toBe(true);

    const stored = run([{ type: 'message', message: message(2, 'assistant', 'Hello') }, { type: 'done', reason: 'completed' }], streaming);
    expect(stored.stream.text).toBe('');
    expect(stored.messages.map((item) => item.content)).toEqual(['Hello']);
    expect(stored.running).toBe(false);
  });

  it('tracks the running tool and clears it with its response', () => {
    const call = { id: 'c1', name: 'search', arguments: { q: 'x' } };
    const running = run([{ type: 'tool_start', call }]);
    expect(running.activeTool).toEqual(call);
    const answered = chatReducer(running, { type: 'message', message: message(3, 'tool-response', 'ok', { tool_call_id: 'c1' }) });
    expect(answered.activeTool).toBeNull();
  });

  it('follows the activity of a sub-agent', () => {
    const state = run([
      { type: 'status', state: 'delegating', agent: 'researcher', conversation_id: 9 },
      { type: 'delegation', agent_id: 4, conversation_id: 9, event: { type: 'token', delta: 'Par' } },
      { type: 'delegation', agent_id: 4, conversation_id: 9, event: { type: 'tool_start', call: { id: 'x', name: 'lookup', arguments: {} } } },
      { type: 'delegation', agent_id: 4, conversation_id: 9, event: { type: 'token', delta: 'is' } },
    ]);
    expect(state.delegations[9]).toMatchObject({ agent: 'researcher', agentId: 4, text: 'Paris', tools: ['lookup'] });
    expect(run([{ type: 'done', reason: 'completed' }], state).delegations).toEqual({});
  });

  it('keeps socket errors until dismissed', () => {
    const state = run([{ type: 'local/sending' }, { type: 'error', error: { code: 'conversation_busy', message: 'Busy' } }]);
    expect(state.error?.code).toBe('conversation_busy');
    expect(state.running).toBe(false);
    expect(chatReducer(state, { type: 'local/dismiss-error' }).error).toBeNull();
  });

  it('replaces a message updated in place', () => {
    const state = run([
      { type: 'message', message: message(1, 'user', 'first') },
      { type: 'message', message: message(1, 'user', 'edited') },
    ]);
    expect(state.messages.map((item) => item.content)).toEqual(['edited']);
  });
});

describe('toBlocks', () => {
  it('attaches tool responses to their calls', () => {
    const blocks = toBlocks([
      message(1, 'user', 'find'),
      message(2, 'tool-calling', null, { tool_calls: [{ id: 'a', name: 'search', arguments: {} }, { id: 'b', name: 'read', arguments: {} }] }),
      message(3, 'tool-response', 'result a', { tool_call_id: 'a' }),
      message(4, 'tool-response', 'stray', { tool_call_id: 'zzz' }),
      message(5, 'assistant', 'done'),
    ]);
    expect(blocks.map((block) => block.kind)).toEqual(['user', 'tools', 'tool-response', 'assistant']);
    const tools = blocks[1];
    if (tools.kind !== 'tools') throw new Error('expected tools');
    expect(tools.calls.map((view) => view.response?.content ?? null)).toEqual(['result a', null]);
  });
});

describe('helpers', () => {
  it('finds the prompt of an answer', () => {
    const messages = [message(1, 'user', 'q1'), message(2, 'assistant', 'a1'), message(3, 'user', 'q2'), message(4, 'assistant', 'a2')];
    expect(promptBefore(messages, 4)?.id).toBe(3);
    expect(promptBefore(messages, 1)).toBeNull();
  });

  it('describes what the agent is doing', () => {
    expect(describeStatus(null, null)).toBe('Thinking');
    expect(describeStatus({ state: 'retrying', attempt: 2, retry: 3, reason: 'timeout', delay: 4 }, null)).toBe(
      'The model failed: timeout. Retrying in 4s (attempt 3 of 4)',
    );
    expect(describeStatus({ state: 'waiting_resources', needs: { vram_mb: 4000 } }, null)).toBe('Waiting for vram_mb to be free');
    expect(describeStatus(null, 'search')).toBe('Running search');
  });
});
