import { useCallback, useMemo, useRef, useState } from 'react';
import { DialogContext, type ConfirmOptions, type PromptOptions } from './dialogContext';
import type { ReactNode } from 'react';
import { Modal } from './Modal';

type Pending =
  | { kind: 'confirm'; options: ConfirmOptions; resolve: (value: boolean) => void }
  | { kind: 'prompt'; options: PromptOptions; resolve: (value: string | null) => void };

function PromptBody({ options, onDone }: { options: PromptOptions; onDone: (value: string | null) => void }) {
  const [value, setValue] = useState(options.initial ?? options.options?.[0]?.value ?? '');
  const input = useRef<HTMLInputElement>(null);
  return (
    <Modal
      title={options.title}
      onClose={() => onDone(null)}
      width={460}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={() => onDone(null)}>
            Cancel
          </button>
          <button type="submit" form="prompt-form" className="btn btn-primary" disabled={!options.options && !value.trim()}>
            {options.confirmLabel ?? 'OK'}
          </button>
        </>
      }
    >
      <form
        id="prompt-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (options.options || value.trim()) onDone(options.options ? value : value.trim());
        }}
      >
        <div className="form-group">
          <label className="form-label" htmlFor="prompt-value">
            {options.label}
          </label>
          {options.options ? (
            <select id="prompt-value" className="form-input" value={value} onChange={(event) => setValue(event.target.value)} autoFocus>
              {options.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="prompt-value"
              ref={input}
              className="form-input"
              value={value}
              placeholder={options.placeholder}
              onChange={(event) => setValue(event.target.value)}
              onFocus={(event) => event.currentTarget.select()}
              autoFocus
            />
          )}
          {options.hint && <div className="form-hint">{options.hint}</div>}
        </div>
      </form>
    </Modal>
  );
}

/** Styled replacements for `window.confirm` and `window.prompt`. */
export function DialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => new Promise<boolean>((resolve) => setPending({ kind: 'confirm', options, resolve })), []);
  const prompt = useCallback((options: PromptOptions) => new Promise<string | null>((resolve) => setPending({ kind: 'prompt', options, resolve })), []);
  const api = useMemo(() => ({ confirm, prompt }), [confirm, prompt]);

  const finish = (value: boolean | string | null) => {
    if (!pending) return;
    (pending.resolve as (value: boolean | string | null) => void)(value);
    setPending(null);
  };

  return (
    <DialogContext.Provider value={api}>
      {children}
      {pending?.kind === 'confirm' && (
        <Modal
          title={pending.options.title}
          onClose={() => finish(false)}
          width={460}
          footer={
            <>
              <button type="button" className="btn btn-ghost" onClick={() => finish(false)}>
                Cancel
              </button>
              <button type="button" className={`btn ${pending.options.danger ? 'btn-danger' : 'btn-primary'}`} onClick={() => finish(true)} autoFocus>
                {pending.options.confirmLabel ?? 'Confirm'}
              </button>
            </>
          }
        >
          {pending.options.message && <div className="muted">{pending.options.message}</div>}
        </Modal>
      )}
      {pending?.kind === 'prompt' && <PromptBody options={pending.options} onDone={finish} />}
    </DialogContext.Provider>
  );
}

