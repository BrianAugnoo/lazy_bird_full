import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { conversations } from '@/api/endpoints/agents';
import { LiveSocket, type SocketStatus } from '@/api/socket';
import type { ConversationDetail } from '@/core/types/api';
import { chatReducer, initialChatState, type ServerEvent } from './state';

/**
 * Live connection to one conversation (`/ws/conversations/{id}`).
 * Commands sent before the socket opens are delivered once it is open.
 */
export function useConversation(conversationId: number | null) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [status, setStatus] = useState<SocketStatus>('closed');
  const socketRef = useRef<LiveSocket | null>(null);
  const outbox = useRef<Record<string, unknown>[]>([]);

  useEffect(() => {
    dispatch({ type: 'local/reset' });
    if (!conversationId) return;
    const socket = new LiveSocket(`/ws/conversations/${conversationId}`, {
      onMessage: (data) => dispatch(data as ServerEvent),
      onStatus: (next) => {
        setStatus(next);
        if (next === 'open') {
          const queued = outbox.current;
          outbox.current = [];
          for (const command of queued) socket.send(command);
        }
      },
    });
    socketRef.current = socket;
    return () => {
      socket.close();
      socketRef.current = null;
      outbox.current = [];
    };
  }, [conversationId]);

  const command = useCallback((payload: Record<string, unknown>) => {
    if (!socketRef.current?.send(payload)) outbox.current.push(payload);
  }, []);

  const send = useCallback(
    (content: string) => {
      dispatch({ type: 'local/sending' });
      command({ type: 'message', content });
    },
    [command],
  );

  const run = useCallback(() => {
    dispatch({ type: 'local/sending' });
    command({ type: 'run' });
  }, [command]);

  const stop = useCallback(() => {
    if (socketRef.current?.send({ type: 'stop' })) return;
    if (conversationId) void conversations.stop(conversationId);
  }, [conversationId]);

  const replace = useCallback((conversation: ConversationDetail) => dispatch({ type: 'local/replace', conversation }), []);
  const dismissError = useCallback(() => dispatch({ type: 'local/dismiss-error' }), []);

  return { state, status, send, run, stop, replace, dismissError };
}

