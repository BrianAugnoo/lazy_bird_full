import { useEffect, useMemo, useRef } from 'react';
import { conversations, messages as messagesApi } from '@/api/endpoints/agents';
import type { Agent, Message } from '@/core/types/api';
import { Icon } from '@/ui/Icon';
import { Markdown } from '@/ui/Markdown';
import { useToast } from '@/ui/toastContext';
import { Composer } from './Composer';
import { MessageList, type MessageActions } from './Messages';
import { describeStatus, promptBefore, toBlocks } from './state';
import { useConversation } from './useConversation';

interface ConversationViewProps {
  conversationId: number;
  agent: Agent | undefined;
  /** Sent as soon as the conversation is connected (first prompt of a new chat). */
  firstMessage: string | null;
  onFirstMessageSent: () => void;
  /** A run ended or the conversation changed: refresh titles and the list of conversations. */
  onActivity: () => void;
  conversationHref: (conversationId: number) => string;
}

const WAITING_ROLES: Message['role'][] = ['user', 'tool-calling', 'tool-response'];

export function ConversationView({ conversationId, agent, firstMessage, onFirstMessageSent, onActivity, conversationHref }: ConversationViewProps) {
  const { state, status, send, run, stop, replace, dismissError } = useConversation(conversationId);
  const toast = useToast();
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const wasRunning = useRef(false);

  useEffect(() => {
    if (firstMessage) {
      send(firstMessage);
      onFirstMessageSent();
    }
    // Only for the conversation that was just created.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    if (wasRunning.current && !state.running) onActivity();
    wasRunning.current = state.running;
  }, [state.running, onActivity]);

  useEffect(() => {
    const node = scroller.current;
    if (node && stickToBottom.current) node.scrollTop = node.scrollHeight;
  }, [state.messages, state.stream, state.status, state.delegations]);

  const blocks = useMemo(() => toBlocks(state.messages), [state.messages]);
  const delegations = useMemo(() => Object.values(state.delegations), [state.delegations]);
  const last = state.messages[state.messages.length - 1];
  const unanswered = !state.running && last !== undefined && WAITING_ROLES.includes(last.role);

  const guard = (action: () => Promise<void>) => () => {
    action().catch((reason) => toast.error(reason));
  };

  const actions: MessageActions = {
    onEdit: (message, content) =>
      guard(async () => {
        await messagesApi.edit(message.id, content);
        replace(await conversations.rewind(conversationId, message.id));
        run();
      })(),
    onRegenerate: (message) =>
      guard(async () => {
        const prompt = promptBefore(state.messages, message.id);
        if (!prompt) return;
        replace(await conversations.rewind(conversationId, prompt.id));
        run();
      })(),
    onDelete: (message) =>
      guard(async () => {
        await messagesApi.remove(message.id);
        replace(await conversations.get(conversationId));
      })(),
    onRetry: run,
    conversationHref,
  };

  const agentProblem = agent && !agent.valid ? Object.values(agent.errors).join(' ') : null;

  return (
    <>
      <div
        className="chat-scroll"
        ref={scroller}
        onScroll={(event) => {
          const node = event.currentTarget;
          stickToBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 120;
        }}
      >
        <div className="chat-column">
          {status !== 'open' && state.messages.length === 0 && (
            <div className="state-loading">
              <span className="spinner" /> Connecting…
            </div>
          )}
          <MessageList blocks={blocks} running={state.running} activeToolId={state.activeTool?.id ?? null} delegations={delegations} actions={actions} />
          {state.running && (
            <div className="msg msg-assistant is-live">
              {state.stream.reasoning && (
                <details className="msg-reasoning" open>
                  <summary>Thinking…</summary>
                  <div className="msg-reasoning-body">{state.stream.reasoning}</div>
                </details>
              )}
              {state.stream.text && <Markdown text={state.stream.text} />}
              <div className="live-status">
                <span className="dot dot-live" />
                {describeStatus(state.status, state.activeTool?.name ?? null)}…
              </div>
            </div>
          )}
          {unanswered && (
            <div className="chat-notice">
              <span>{agent?.name ?? 'The agent'} has not answered yet.</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={run}>
                <Icon name="play" /> Answer now
              </button>
            </div>
          )}
          {state.error && (
            <div className="alert alert-error row-between" role="alert">
              <span>{state.error.message}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={dismissError} aria-label="Dismiss">
                <Icon name="close" />
              </button>
            </div>
          )}
        </div>
      </div>
      {status === 'closed' && <div className="chat-connection">Connection lost, reconnecting…</div>}
      <Composer
        placeholder={`Message ${agent?.name ?? 'the agent'}…`}
        running={state.running}
        disabled={Boolean(agentProblem)}
        disabledReason={agentProblem ? `Fix this agent first: ${agentProblem}` : undefined}
        onSend={(content) => {
          stickToBottom.current = true;
          send(content);
        }}
        onStop={stop}
      />
    </>
  );
}
