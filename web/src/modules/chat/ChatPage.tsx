import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { agents as agentsApi, conversations as conversationsApi, sessions as sessionsApi } from '@/api/endpoints/agents';
import { buildHash, useRoute, useRouteActions } from '@/core/router';
import type { Agent, Conversation } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { Icon } from '@/ui/Icon';
import { useToast } from '@/ui/toastContext';
import { useDialogs } from '@/ui/dialogContext';
import { AgentEditor } from './AgentEditor';
import { Composer } from './Composer';
import { ConversationView } from './ConversationView';
import { AddAgentDialog, NewSessionDialog, SessionSettings } from './SessionDialogs';
import { SessionRail } from './SessionRail';

type Dialog = { kind: 'new-session' } | { kind: 'add-agent' } | { kind: 'session' } | { kind: 'agent'; agent: Agent | null } | null;

const toNumber = (value: string | undefined) => (value && Number.isFinite(Number(value)) ? Number(value) : null);

export function ChatPage() {
  const route = useRoute();
  const { setParams } = useRouteActions();
  const dialogs = useDialogs();
  const toast = useToast();
  const sessionId = toNumber(route.params.session);
  const conversationId = toNumber(route.params.conversation);
  const agentParam = toNumber(route.params.agent);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [railOpen, setRailOpen] = useState(() => window.matchMedia('(min-width: 861px)').matches);
  const layout = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const observer = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width > 0 && width < 720) setRailOpen(false);
    });
    if (layout.current) observer.observe(layout.current);
    return () => observer.disconnect();
  }, []);
  const [firstMessage, setFirstMessage] = useState<{ conversationId: number; content: string } | null>(null);

  const sessions = useResource(sessionsApi.list, []);
  const session = sessions.data?.find((item) => item.id === sessionId);
  const agents = useResource(() => (sessionId ? agentsApi.ofSession(sessionId) : Promise.resolve([] as Agent[])), [sessionId]);
  const conversations = useResource(() => conversationsApi.list(), []);

  // Open the most recent session when none is chosen (or the chosen one is gone).
  useEffect(() => {
    const list = sessions.data;
    if (!list || list.length === 0 || session) return;
    const latest = [...list].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];
    setParams({ session: latest.id, conversation: null, agent: null });
  }, [sessions.data, session, setParams]);

  const agentList = useMemo(() => agents.data ?? [], [agents.data]);
  const agentIds = useMemo(() => new Set(agentList.map((agent) => agent.id)), [agentList]);
  const sessionConversations = useMemo(
    () => (conversations.data ?? []).filter((conversation) => agentIds.has(conversation.agent_id)).sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [conversations.data, agentIds],
  );
  const conversation = sessionConversations.find((item) => item.id === conversationId);
  const master = agentList.find((agent) => agent.master) ?? agentList[0];
  const activeAgent = agentList.find((agent) => agent.id === (conversation?.agent_id ?? agentParam)) ?? master;

  // A conversation created meanwhile (e.g. by a delegation) is not listed yet.
  const lookedUp = useRef<number | null>(null);
  useEffect(() => {
    if (conversationId && conversations.data && !conversation && lookedUp.current !== conversationId) {
      lookedUp.current = conversationId;
      void conversations.reload();
    }
  }, [conversationId, conversations, conversation]);

  const refresh = useCallback(() => {
    void conversations.reload();
  }, [conversations]);

  const openConversation = (id: number | null, agentId: number | null = null) => {
    setParams({ conversation: id, agent: agentId });
  };
  const conversationHref = useCallback((id: number) => buildHash('chat', { session: sessionId, conversation: id }), [sessionId]);

  const startConversation = async (content: string) => {
    if (!activeAgent) return;
    try {
      const created = await conversationsApi.create(activeAgent.id);
      setFirstMessage({ conversationId: created.id, content });
      await conversations.reload();
      openConversation(created.id);
    } catch (reason) {
      toast.error(reason);
    }
  };

  const renameConversation = async (item: Conversation) => {
    const title = (await dialogs.prompt({ title: 'Rename conversation', label: 'Conversation title', initial: item.title, confirmLabel: 'Rename' }))?.trim();
    if (!title || title === item.title) return;
    try {
      await conversationsApi.rename(item.id, title);
      refresh();
    } catch (reason) {
      toast.error(reason);
    }
  };

  const deleteConversation = async (item: Conversation) => {
    if (!await dialogs.confirm({ title: `Delete ${item.title}?`, message: 'Messages in this conversation will be deleted.', confirmLabel: 'Delete', danger: true })) return;
    try {
      await conversationsApi.remove(item.id);
      if (item.id === conversationId) openConversation(null, item.agent_id);
      refresh();
    } catch (reason) {
      toast.error(reason);
    }
  };

  if (sessions.data && sessions.data.length === 0) {
    return (
      <div className="chat-welcome">
        <Icon name="bird" size={44} className="chat-welcome-logo" />
        <h1 className="page-title">Start your first session</h1>
        <p className="page-description">A session is a team of agents. Pick a preset to get a ready-made team, or build your own.</p>
        <button type="button" className="btn btn-primary" onClick={() => setDialog({ kind: 'new-session' })}>
          <Icon name="plus" /> New session
        </button>
        {dialog?.kind === 'new-session' && (
          <NewSessionDialog
            onClose={() => setDialog(null)}
            onCreated={async (created) => {
              setDialog(null);
              await sessions.reload();
              setParams({ session: created.id, conversation: null, agent: null });
            }}
          />
        )}
      </div>
    );
  }

  return (
    <div ref={layout} className={`chat-layout ${railOpen ? 'show-rail' : 'rail-collapsed'}`}>
      <AsyncState {...sessions} onRetry={sessions.reload}>
        {(list) => (
          <SessionRail
            sessions={list}
            session={session}
            agents={agentList}
            conversations={sessionConversations}
            selectedConversation={conversation?.id ?? null}
            selectedAgent={activeAgent?.id ?? null}
            onSelectSession={(id) => setParams({ session: id, conversation: null, agent: null })}
            onNewSession={() => setDialog({ kind: 'new-session' })}
            onSessionSettings={() => setDialog({ kind: 'session' })}
            onSelectConversation={(item) => openConversation(item.id)}
            onNewConversation={(agent) => openConversation(null, agent.id)}
            onAgentSettings={(agent) => setDialog({ kind: 'agent', agent })}
            onAddAgent={() => setDialog({ kind: 'add-agent' })}
            onRenameConversation={renameConversation}
            onDeleteConversation={deleteConversation}
            onClose={() => setRailOpen(false)}
          />
        )}
      </AsyncState>

      <section className="chat-main">
        <header className="chat-header">
          <button type="button" className="btn btn-ghost btn-icon" onClick={() => setRailOpen(!railOpen)} aria-expanded={railOpen} aria-label={railOpen ? 'Hide sessions and conversations' : 'Show sessions and conversations'}>
            <Icon name="panel" />
          </button>
          <div className="chat-header-title">
            <span className="truncate">{conversation?.title ?? (activeAgent ? `New chat with ${activeAgent.name}` : session?.title ?? 'Chat')}</span>
          </div>
          <div className="row">
            {conversation && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => openConversation(null, conversation.agent_id)} aria-label="New chat" title="New chat">
                <Icon name="plus" /> <span className="btn-label">New chat</span>
              </button>
            )}
            {activeAgent && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDialog({ kind: 'agent', agent: activeAgent })} title="Model, instructions, tools…" aria-label={`Settings of ${activeAgent.name}`}>
                <Icon name="settings" /> <span className="btn-label">{activeAgent.name}</span>
              </button>
            )}
          </div>
        </header>

        {agents.data && agentList.length === 0 ? (
          <div className="chat-empty">
            <h2 className="section-title">This session has no agent yet</h2>
            <p className="muted">Add an agent to start chatting.</p>
            <button type="button" className="btn btn-primary" onClick={() => setDialog({ kind: 'add-agent' })}>
              <Icon name="plus" /> Add an agent
            </button>
          </div>
        ) : conversation ? (
          <ConversationView
            key={conversation.id}
            conversationId={conversation.id}
            agent={agentList.find((agent) => agent.id === conversation.agent_id)}
            firstMessage={firstMessage?.conversationId === conversation.id ? firstMessage.content : null}
            onFirstMessageSent={() => setFirstMessage(null)}
            onActivity={refresh}
            conversationHref={conversationHref}
          />
        ) : (
          <>
            <div className="chat-scroll">
              <div className="chat-column chat-start">
                {activeAgent && (
                  <>
                    <h2 className="chat-start-title">What should {activeAgent.name} do?</h2>
                    {activeAgent.description && <p className="muted">{activeAgent.description}</p>}
                    {activeAgent.sub_agents_ids.length > 0 && (
                      <p className="muted small">
                        Can delegate to{' '}
                        {activeAgent.sub_agents_ids
                          .map((id) => agentList.find((agent) => agent.id === id)?.name)
                          .filter(Boolean)
                          .join(', ')}
                        .
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>
            <Composer
              placeholder={`Message ${activeAgent?.name ?? 'the agent'}…`}
              running={false}
              disabled={!activeAgent || !activeAgent.valid}
              disabledReason={activeAgent && !activeAgent.valid ? `Fix this agent first: ${Object.values(activeAgent.errors).join(' ')}` : 'Add an agent first'}
              onSend={startConversation}
              onStop={() => undefined}
            />
          </>
        )}
      </section>

      {dialog?.kind === 'new-session' && (
        <NewSessionDialog
          onClose={() => setDialog(null)}
          onCreated={async (created) => {
            setDialog(null);
            await sessions.reload();
            setParams({ session: created.id, conversation: null, agent: null });
          }}
        />
      )}
      {dialog?.kind === 'add-agent' && sessionId && (
        <AddAgentDialog
          sessionId={sessionId}
          onClose={() => setDialog(null)}
          onBlank={() => setDialog({ kind: 'agent', agent: null })}
          onCreated={async (agent) => {
            setDialog(null);
            toast.show(`${agent.name} added`);
            await agents.reload();
            openConversation(null, agent.id);
          }}
        />
      )}
      {dialog?.kind === 'session' && session && (
        <SessionSettings
          session={session}
          sessionAgents={agentList}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            void sessions.reload();
          }}
          onDeleted={async () => {
            setDialog(null);
            setParams({ session: null, conversation: null, agent: null });
            await sessions.reload();
          }}
        />
      )}
      {dialog?.kind === 'agent' && sessionId && (
        <AgentEditor
          agent={dialog.agent}
          sessionId={sessionId}
          sessionAgents={agentList}
          onClose={() => setDialog(null)}
          onSaved={async (saved) => {
            setDialog(null);
            await agents.reload();
            if (!dialog.agent) openConversation(null, saved.id);
          }}
          onDeleted={async (id) => {
            setDialog(null);
            if (activeAgent?.id === id) openConversation(null, null);
            await agents.reload();
            refresh();
          }}
        />
      )}
    </div>
  );
}
