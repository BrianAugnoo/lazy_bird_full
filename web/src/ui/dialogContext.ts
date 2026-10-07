import { createContext, useContext, type ReactNode } from 'react';

export interface ConfirmOptions {
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
}

export interface PromptOptions {
  title: string;
  label: string;
  initial?: string;
  placeholder?: string;
  confirmLabel?: string;
  hint?: ReactNode;
  /** Choices instead of free text. */
  options?: Array<{ value: string; label: string }>;
}

export interface DialogApi {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  /** Resolves with the text entered, or null when cancelled. */
  prompt: (options: PromptOptions) => Promise<string | null>;
}

export const DialogContext = createContext<DialogApi>({
  confirm: async (options) => window.confirm(options.title),
  prompt: async (options) => window.prompt(options.label, options.initial),
});

/** Styled `confirm` / `prompt` (see `DialogProvider`). */
export function useDialogs(): DialogApi {
  return useContext(DialogContext);
}
