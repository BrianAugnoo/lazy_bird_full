import { createContext, useContext } from 'react';

export type Tone = 'info' | 'success' | 'error';

export interface ToastApi {
  show: (message: string, tone?: Tone) => void;
  /** Show an error (an `ApiError` message, or anything else as text). */
  error: (reason: unknown) => void;
}

export const ToastContext = createContext<ToastApi>({ show: () => undefined, error: () => undefined });

export function useToast(): ToastApi {
  return useContext(ToastContext);
}
