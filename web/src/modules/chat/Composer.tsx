import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/ui/Icon';
import { Popover } from '@/ui/Popover';
import { useRouteActions } from '@/core/router';

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
  const [menuOpen, setMenuOpen] = useState(false);
  const { active } = useRouteActions();
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const node = area.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${Math.min(node.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    if (!running || !active) return;
    const handler = (event: KeyboardEvent) => {
      const overlayOpen = [...document.querySelectorAll('[role="dialog"]')].some(dialog => !dialog.closest('[hidden]'));
      if (event.key === 'Escape' && !event.defaultPrevented && !overlayOpen) onStop();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [running, onStop, active]);

  const submit = () => {
    const content = text.trim();
    if (!content || running || disabled) return;
    onSend(content);
    setText('');
  };

  return (
    <div className="composer">
      <div className={`composer-box ${disabled ? 'is-disabled' : ''}`}>
        <div className="composer-add">
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Add to message" aria-haspopup="dialog" aria-expanded={menuOpen} title="Add to message" onClick={() => setMenuOpen(!menuOpen)}><Icon name="plus" size={20} /></button>
          {menuOpen && <Popover label="Add to message" onClose={() => setMenuOpen(false)} className="composer-menu">
            <div className="popover-caption">More ways to create</div>
            {[{ label: 'Import files', icon: 'upload' as const }, { label: 'Import folders', icon: 'files' as const }, { label: 'Create an image', icon: 'image' as const }].map(item => <button type="button" key={item.label} className="popover-item" aria-disabled="true" title="Coming soon — unavailable in chat"><Icon name={item.icon} size={17} /><span>{item.label}</span><small className="soon-badge">Coming soon</small></button>)}
            <p className="popover-note">These features are not available yet.</p>
          </Popover>}
        </div>
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
        <button type="button" className="btn btn-ghost btn-icon composer-microphone" aria-label="Audio — coming soon" aria-disabled="true" title="Audio — coming soon"><Icon name="microphone" size={19} /></button>
        {running ? (
          <button type="button" className="btn btn-secondary btn-icon composer-button" onClick={onStop} title="Stop (Esc)" aria-label="Stop">
            <Icon name="stop" size={16} />
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-icon composer-button" onClick={submit} disabled={!text.trim() || disabled} title="Send (Enter)" aria-label="Send">
            <Icon name="send" size={21} />
          </button>
        )}
      </div>
      <div className="composer-hint">
        <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line{running && <> · <kbd>Esc</kbd> to stop</>}
      </div>
    </div>
  );
}
