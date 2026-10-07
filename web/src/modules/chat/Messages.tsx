import { useState } from 'react';
import { buildHash } from '@/core/router';
import type { Message, ToolCallMeta } from '@/core/types/api';
import { Icon } from '@/ui/Icon';
import { Markdown } from '@/ui/Markdown';
import type { Block, LiveDelegation, ToolCallView } from './state';

const ERROR_TITLES: Record<string, string> = {
  no_inference_preset: 'This agent has no model to answer with',
  agent_without_inference: 'This agent has no model to answer with',
  resources_busy: 'The model stayed busy for too long',
  max_iterations: 'The agent took too many steps',
  hook_failed: 'A hook failed before the answer',
  delegation_failed: 'A sub-agent could not finish its task',
};

export interface MessageActions {
  onEdit: (message: Message, content: string) => void;
  onRegenerate: (message: Message) => void;
  onDelete: (message: Message) => void;
  onRetry: () => void;
  /** Link to another conversation of the session (delegations). */
  conversationHref: (conversationId: number) => string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm"
      onClick={() => {
        void navigator.clipboard?.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1200);
      }}
    >
      <Icon name={copied ? 'check' : 'copy'} /> {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function Reasoning({ text, live = false }: { text: string; live?: boolean }) {
  if (!text.trim()) return null;
  return (
    <details className="msg-reasoning" open={live}>
      <summary>{live ? 'Thinking…' : 'Thought process'}</summary>
      <div className="msg-reasoning-body">{text}</div>
    </details>
  );
}

function UserMessage({ message, actions, busy }: { message: Message; actions: MessageActions; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content ?? '');
  if (editing) {
    return (
      <div className="msg msg-user is-editing">
        <textarea className="form-textarea" value={draft} onChange={(event) => setDraft(event.target.value)} rows={Math.min(12, draft.split('\n').length + 1)} autoFocus />
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={!draft.trim()}
            onClick={() => {
              setEditing(false);
              actions.onEdit(message, draft.trim());
            }}
          >
            Save and resend
          </button>
        </div>
        <p className="form-hint">The messages after this one are deleted and the agent answers again.</p>
      </div>
    );
  }
  return (
    <div className="msg msg-user">
      <div className="msg-user-text">{message.content}</div>
      <div className="msg-actions">
        <CopyButton text={message.content ?? ''} />
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setEditing(true)}>
          <Icon name="edit" /> Edit
        </button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => actions.onDelete(message)}>
          <Icon name="trash" /> Delete
        </button>
      </div>
    </div>
  );
}

function AssistantMessage({ message, actions, busy, last }: { message: Message; actions: MessageActions; busy: boolean; last: boolean }) {
  const meta = message.meta ?? {};
  const usage = meta.usage as { total_tokens?: number } | null | undefined;
  return (
    <div className="msg msg-assistant">
      <Reasoning text={String(meta.reasoning ?? '')} />
      <Markdown text={message.content ?? ''} />
      {meta.stopped === true && <div className="msg-note">Stopped before the end.</div>}
      <div className="msg-actions">
        <CopyButton text={message.content ?? ''} />
        {last && (
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => actions.onRegenerate(message)}>
            <Icon name="refresh" /> Regenerate
          </button>
        )}
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => actions.onDelete(message)}>
          <Icon name="trash" /> Delete
        </button>
        <span className="msg-meta">
          {[meta.model, usage?.total_tokens ? `${usage.total_tokens} tokens` : null].filter(Boolean).join(' · ')}
        </span>
      </div>
    </div>
  );
}

function argumentSummary(call: ToolCallMeta): string {
  const args = call.arguments ?? {};
  if (call.name === 'delegate_to_agent') return `${String(args.agent ?? '?')}: ${String(args.task ?? '')}`;
  const values = Object.values(args)
    .filter((value) => value !== null && value !== undefined && typeof value !== 'object')
    .map(String);
  return values.join(', ');
}

function pretty(value: unknown): string {
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
}

function LiveDelegationView({ delegation, href }: { delegation: LiveDelegation; href: string }) {
  return (
    <div className="tool-delegation">
      <div className="row-between small">
        <span>
          <span className="dot dot-live" /> <strong>{delegation.agent ?? 'Sub-agent'}</strong> {delegation.status ?? 'is working'}
          {delegation.tools.length > 0 && <span className="muted"> · used {delegation.tools.join(', ')}</span>}
        </span>
        <a href={href}>Open its conversation</a>
      </div>
      {delegation.text && <div className="tool-delegation-text">{delegation.text}</div>}
    </div>
  );
}

function ToolCard({
  view,
  running,
  delegations,
  actions,
}: {
  view: ToolCallView;
  running: boolean;
  delegations: LiveDelegation[];
  actions: MessageActions;
}) {
  const { call, response } = view;
  const status = (response?.meta?.status as string | undefined) ?? (running ? 'running' : 'waiting');
  const [open, setOpen] = useState(false);
  const delegation = (response?.meta?.delegation ?? (response?.meta?.error as { details?: { delegation?: unknown } } | undefined)?.details?.delegation) as
    | { conversation_id: number; agent: string }
    | undefined;
  const isDelegation = call.name === 'delegate_to_agent';
  const dot = status === 'ok' ? 'dot-success' : status === 'error' ? 'dot-error' : status === 'running' ? 'dot-live' : 'dot-muted';
  const live = isDelegation && running ? delegations[delegations.length - 1] : undefined;

  return (
    <div className={`tool-card is-${status}`}>
      <button type="button" className="tool-card-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={`dot ${dot}`} />
        <span className="tool-card-name">{isDelegation ? 'Delegated' : call.name}</span>
        <span className="tool-card-args">{argumentSummary(call)}</span>
        {status === 'cancelled' && <span className="chip chip-muted">cancelled</span>}
        {status === 'waiting' && <span className="chip chip-muted">not run</span>}
        <Icon name={open ? 'chevronDown' : 'chevronRight'} size={14} />
      </button>
      {live && <LiveDelegationView delegation={live} href={actions.conversationHref(live.conversationId)} />}
      {delegation && (
        <div className="tool-card-link">
          <a href={actions.conversationHref(delegation.conversation_id)}>
            Open {delegation.agent}'s conversation <Icon name="external" size={13} />
          </a>
        </div>
      )}
      {open && (
        <div className="tool-card-body">
          <div className="tool-card-label">Arguments</div>
          <pre className="code">{pretty(call.arguments)}</pre>
          <div className="tool-card-label">Result</div>
          {response ? <pre className="code tool-card-result">{pretty(response.content)}</pre> : <div className="muted small">No result yet.</div>}
        </div>
      )}
    </div>
  );
}

function ErrorMessage({ message, actions, canRetry }: { message: Message; actions: MessageActions; canRetry: boolean }) {
  const code = String(message.meta?.code ?? 'error');
  return (
    <div className="msg msg-error" role="alert">
      <div className="msg-error-title">
        <Icon name="alert" size={16} /> {ERROR_TITLES[code] ?? 'The agent could not answer'}
      </div>
      <div className="msg-error-text">{message.content}</div>
      {(code === 'no_inference_preset' || code === 'agent_without_inference') && (
        <a href={buildHash('inference')}>Set up an inference preset</a>
      )}
      <div className="msg-actions is-visible">
        {canRetry && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={actions.onRetry}>
            <Icon name="refresh" /> Retry
          </button>
        )}
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => actions.onDelete(message)}>
          <Icon name="trash" /> Dismiss
        </button>
        <span className="msg-meta mono">{code}</span>
      </div>
    </div>
  );
}

interface MessageListProps {
  blocks: Block[];
  running: boolean;
  activeToolId: string | null;
  delegations: LiveDelegation[];
  actions: MessageActions;
}

export function MessageList({ blocks, running, activeToolId, delegations, actions }: MessageListProps) {
  const lastIndex = blocks.length - 1;
  const lastAnswer = blocks.reduce((found, block, index) => (block.kind === 'assistant' ? index : found), -1);
  return (
    <>
      {blocks.map((block, index) => {
        const key = block.message.id;
        switch (block.kind) {
          case 'system':
            return (
              <details key={key} className="msg-system">
                <summary>Instructions given to the agent</summary>
                <Markdown text={block.message.content ?? ''} />
              </details>
            );
          case 'user':
            return <UserMessage key={key} message={block.message} actions={actions} busy={running} />;
          case 'assistant':
            return <AssistantMessage key={key} message={block.message} actions={actions} busy={running} last={index === lastAnswer} />;
          case 'error':
            return <ErrorMessage key={key} message={block.message} actions={actions} canRetry={index === lastIndex && !running} />;
          case 'tools':
            return (
              <div key={key} className="msg msg-tools">
                <Reasoning text={String(block.message.meta?.reasoning ?? '')} />
                {block.message.content && <Markdown text={block.message.content} />}
                {block.calls.map((view) => (
                  <ToolCard
                    key={view.call.id}
                    view={view}
                    running={running && !view.response && (activeToolId === view.call.id || activeToolId === null)}
                    delegations={delegations}
                    actions={actions}
                  />
                ))}
              </div>
            );
          case 'tool-response':
            return (
              <div key={key} className="tool-card is-orphan">
                <div className="tool-card-head">
                  <span className="dot dot-muted" />
                  <span className="tool-card-name">{String(block.message.meta?.name ?? 'tool')}</span>
                  <span className="tool-card-args">{block.message.content}</span>
                </div>
              </div>
            );
          default:
            return null;
        }
      })}
    </>
  );
}
