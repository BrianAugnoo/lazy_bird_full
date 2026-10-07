import { getApiBaseUrl } from './client';

/** WebSocket URL of a backend path, following the HTTP base URL (proxied `/api` in development). */
export function socketUrl(path: string): string {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  if (base.startsWith('/')) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${base}${suffix}`;
  }
  return `${base.replace(/^http/, 'ws')}${suffix}`;
}

export type SocketStatus = 'connecting' | 'open' | 'closed';

interface SocketHandlers {
  onMessage: (data: unknown) => void;
  onStatus?: (status: SocketStatus) => void;
}

/** A JSON WebSocket that reconnects (1s, 2s, 4s… up to 10s) until `close()` is called. */
export class LiveSocket {
  private socket: WebSocket | null = null;
  private retryDelay = 1000;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;
  status: SocketStatus = 'connecting';
  private readonly path: string;
  private readonly handlers: SocketHandlers;

  constructor(path: string, handlers: SocketHandlers) {
    this.path = path;
    this.handlers = handlers;
    this.connect();
  }

  private setStatus(status: SocketStatus) {
    this.status = status;
    this.handlers.onStatus?.(status);
  }

  private connect() {
    if (this.closed || typeof WebSocket === 'undefined') return;
    this.setStatus('connecting');
    const socket = new WebSocket(socketUrl(this.path));
    this.socket = socket;
    socket.onopen = () => {
      this.retryDelay = 1000;
      this.setStatus('open');
    };
    socket.onmessage = (event) => {
      let data: unknown;
      try {
        data = JSON.parse(String(event.data));
      } catch {
        return;
      }
      this.handlers.onMessage(data);
    };
    socket.onclose = () => {
      this.socket = null;
      this.setStatus('closed');
      if (this.closed) return;
      this.retryTimer = setTimeout(() => this.connect(), this.retryDelay);
      this.retryDelay = Math.min(this.retryDelay * 2, 10000);
    };
    socket.onerror = () => socket.close();
  }

  /** Send a JSON command; returns false when the socket is not open. */
  send(command: unknown): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(command));
    return true;
  }

  close() {
    this.closed = true;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.socket?.close();
    this.socket = null;
  }
}
