import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/ui/Icon';

interface ComposerProps {
  placeholder: string;
  running: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onSend: (content: string) => void;
  onStop: () => void;
}

/** Prompt box: Enter sends, Shift+Enter adds a line, Escape stops the agent. */
export function Composer({ placeholder, running, disabled = false, disabledReason, onSend, onStop }: ComposerProps) {
  const [text, setText] = useState('');
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const node = area.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${Math.min(node.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    if (!running) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onStop();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [running, onStop]);

  const submit = () => {
    const content = text.trim();
    if (!content || running || disabled) return;
    onSend(content);
    setText('');
  };

  return (
    <div className="composer">
      <div className={`composer-box ${disabled ? 'is-disabled' : ''}`}>
        <textarea
          ref={area}
          className="composer-input"
          rows={1}
          value={text}
          placeholder={disabled && disabledReason ? disabledReason : placeholder}
          disabled={disabled}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submit();
            }
          }}
          aria-label="Message"
        />
        {running ? (
          <button type="button" className="btn btn-secondary composer-button" onClick={onStop} title="Stop (Esc)">
            <Icon name="stop" /> Stop
          </button>
        ) : (
          <button type="button" className="btn btn-primary composer-button" onClick={submit} disabled={!text.trim() || disabled} title="Send (Enter)">
            <Icon name="send" /> Send
          </button>
        )}
      </div>
      <div className="composer-hint">
        <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line{running && <> · <kbd>Esc</kbd> to stop</>}
      </div>
    </div>
  );
}
