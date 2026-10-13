import { useState } from 'react';
import type { Agent, Conversation, Session } from '@/core/types/api';
import { Icon } from '@/ui/Icon';
import { SearchInput } from '@/ui/SearchInput';
import { agentTree, relativeTime } from './tree';

interface SessionRailProps {
  sessions: Session[];
  session: Session | undefined;
  agents: Agent[];
  conversations: Conversation[];
  selectedConversation: number | null;
  selectedAgent: number | null;
  onSelectSession: (id: number) => void;
  onNewSession: () => void;
  onSessionSettings: () => void;
  onSelectConversation: (conversation: Conversation) => void;
  onNewConversation: (agent: Agent) => void;
  onAgentSettings: (agent: Agent) => void;
  onAddAgent: () => void;
  onRenameConversation: (conversation: Conversation) => void;
  onDeleteConversation: (conversation: Conversation) => void;
  /** Close the rail (narrow screens, where it covers the chat). */
  onClose?: () => void;
}

const COLLAPSED_LIMIT = 6;

export function SessionRail(props: SessionRailProps) {
  const { sessions, session, agents, conversations, selectedConversation, selectedAgent } = props;
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [search, setSearch] = useState('');
  const [sessionSearch, setSessionSearch] = useState('');
  const needle = search.toLowerCase().trim();
  const matches = conversations.filter(item => `${item.title} ${agents.find(agent => agent.id === item.agent_id)?.name ?? ''}`.toLowerCase().includes(needle));

  return (
    <aside className="chat-rail" aria-label="Sessions and conversations">
      <div className="rail-search"><SearchInput label="Search sessions" value={sessionSearch} onChange={setSessionSearch} /></div>
      <div className="chat-rail-head">
        <select
          className="form-input"
          value={session?.id ?? ''}
          onChange={(event) => props.onSelectSession(Number(event.target.value))}
          aria-label="Session"
        >
          {sessions.filter(item => item.id === session?.id || item.title.toLowerCase().includes(sessionSearch.toLowerCase())).map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-ghost btn-icon" onClick={props.onSessionSettings} title="Session settings" aria-label="Session settings" disabled={!session}>
          <Icon name="settings" />
        </button>
        <button type="button" className="btn btn-secondary btn-icon" onClick={props.onNewSession} title="New session" aria-label="New session">
          <Icon name="plus" />
        </button>
        {props.onClose && (
          <button type="button" className="btn btn-ghost btn-icon" onClick={props.onClose} aria-label="Hide sessions and conversations">
            <Icon name="close" />
          </button>
        )}
      </div>
      <div className="rail-search"><SearchInput label="Search conversations and agents" value={search} onChange={setSearch} /></div>

      <div className="chat-rail-body">
        {agentTree(agents).map(({ agent, depth }) => {
          const own = matches.filter((conversation) => conversation.agent_id === agent.id);
          if (needle && own.length === 0 && !agent.name.toLowerCase().includes(needle)) return null;
          const showAll = expanded[agent.id];
          const shown = showAll ? own : own.slice(0, COLLAPSED_LIMIT);
          return (
            <div key={agent.id} className="rail-agent" style={{ marginLeft: depth * 12 }}>
              <div className={`rail-agent-head ${selectedAgent === agent.id && !selectedConversation ? 'is-active' : ''}`}>
                <span className={`rail-agent-name ${agent.valid ? '' : 'is-invalid'}`} title={agent.valid ? agent.description ?? '' : Object.values(agent.errors).join(' ')}>
                  {depth > 0 && <span className="rail-branch">↳</span>}
                  {agent.name}
                  {agent.master && <span className="chip chip-accent">master</span>}
                  {!agent.valid && <Icon name="alert" size={14} className="text-error" />}
                </span>
                <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => props.onNewConversation(agent)} title={`New chat with ${agent.name}`} aria-label={`New chat with ${agent.name}`}>
                  <Icon name="plus" />
                </button>
                <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => props.onAgentSettings(agent)} title="Agent settings" aria-label={`Settings of ${agent.name}`}>
                  <Icon name="settings" />
                </button>
              </div>
              {shown.map((conversation) => (
                <div key={conversation.id} className={`rail-conversation ${selectedConversation === conversation.id ? 'is-active' : ''}`}>
                  <button type="button" className="rail-conversation-main" onClick={() => props.onSelectConversation(conversation)}>
                    {conversation.running && <span className="dot dot-live" />}
                    <span className="truncate">{conversation.title}</span>
                    <span className="rail-time">{relativeTime(conversation.updated_at)}</span>
                  </button>
                  <span className="rail-conversation-actions">
                    <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => props.onRenameConversation(conversation)} aria-label="Rename">
                      <Icon name="edit" size={14} />
                    </button>
                    <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => props.onDeleteConversation(conversation)} aria-label="Delete">
                      <Icon name="trash" size={14} />
                    </button>
                  </span>
                </div>
              ))}
              {own.length > COLLAPSED_LIMIT && (
                <button type="button" className="rail-more" onClick={() => setExpanded({ ...expanded, [agent.id]: !showAll })}>
                  {showAll ? 'Show less' : `Show ${own.length - COLLAPSED_LIMIT} more`}
                </button>
              )}
            </div>
          );
        })}
        {needle && matches.length === 0 && !agents.some(agent => agent.name.toLowerCase().includes(needle)) && <p className="rail-no-results muted small">No matching conversations or agents.</p>}
        <button type="button" className="btn btn-ghost btn-sm rail-add" onClick={props.onAddAgent} disabled={!session}>
          <Icon name="plus" /> Add an agent
        </button>
      </div>
    </aside>
  );
}
