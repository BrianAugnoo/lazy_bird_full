import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { ToastContext, type Tone, type ToastApi } from './toastContext';

interface Toast {
  id: number;
  tone: Tone;
  message: string;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), []);
  const show = useCallback(
    (message: string, tone: Tone = 'success') => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current.slice(-3), { id, tone, message }]);
      window.setTimeout(() => dismiss(id), tone === 'error' ? 7000 : 3500);
    },
    [dismiss],
  );
  const api = useMemo<ToastApi>(
    () => ({ show, error: (reason) => show(reason instanceof Error ? reason.message : String(reason), 'error') }),
    [show],
  );
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`} role={toast.tone === 'error' ? 'alert' : 'status'}>
            <span className="grow">{toast.message}</span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => dismiss(toast.id)} aria-label="Dismiss">
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

