import { getApiBaseUrl } from './client';
import type { FileProgressItem, UploadProgressPayload } from '@/core/types/api';

type ProgressListener = (files: FileProgressItem[]) => void;

class ProgressWebSocketManager {
  private ws: WebSocket | null = null;
  private listeners: Set<ProgressListener> = new Set();
  private reconnectTimeout: any = null;
  private isExplicitlyClosed = false;
  private isConnected = false;

  public subscribe(listener: ProgressListener): () => void {
    this.listeners.add(listener);
    if (!this.ws && !this.isExplicitlyClosed) {
      this.connect();
    }
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) {
        this.disconnect();
      }
    };
  }

  public connect(): void {
    if (typeof window === 'undefined' || !window.WebSocket) return;
    this.isExplicitlyClosed = false;

    try {
      const baseUrl = getApiBaseUrl();
      const wsUrl = baseUrl.startsWith('/')
        ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${baseUrl}/ws/upload-progress`
        : `${baseUrl.startsWith('https') ? 'wss:' : 'ws:'}//${baseUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')}/ws/upload-progress`;

      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.isConnected = true;
      };

      this.ws.onmessage = (event) => {
        try {
          const payload: UploadProgressPayload = JSON.parse(event.data);
          if (payload && Array.isArray(payload.files)) {
            this.notifyListeners(payload.files);
          }
        } catch (err) {
          console.warn('Erreur décodage WebSocket upload-progress:', err);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.ws = null;
        if (!this.isExplicitlyClosed && this.listeners.size > 0) {
          // Reconnexion automatique après 2 secondes
          this.reconnectTimeout = setTimeout(() => {
            this.connect();
          }, 2000);
        }
      };

      this.ws.onerror = () => {
        // En cas d'erreur de connexion, fermer le socket
        this.ws?.close();
      };
    } catch {
      // Ignorer si échec d'instanciation WebSocket
    }
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }

  public getStatus(): boolean {
    return this.isConnected;
  }

  private notifyListeners(files: FileProgressItem[]): void {
    for (const listener of this.listeners) {
      try {
        listener(files);
      } catch (err) {
        console.error('Erreur listener WebSocket:', err);
      }
    }
  }
}

export const progressWs = new ProgressWebSocketManager();
