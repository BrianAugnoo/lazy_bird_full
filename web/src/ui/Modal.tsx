import { useEffect, useRef, type ReactNode } from 'react';
import { Icon } from './Icon';

/** Open overlays, the last opened on top: Escape only closes that one. */
const open: object[] = [];

function useEscape(onClose: () => void) {
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  });
  useEffect(() => {
    const overlay = {};
    open.push(overlay);
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open[open.length - 1] === overlay) close.current();
    };
    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      open.splice(open.indexOf(overlay), 1);
    };
  }, []);
}

interface OverlayProps {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
  width?: number;
}

/** Centered dialog; closes with Escape or a click outside. */
export function Modal({ title, subtitle, onClose, footer, children, width = 640 }: OverlayProps) {
  useEscape(onClose);
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-window" style={{ maxWidth: width }} role="dialog" aria-modal="true">
        <div className="modal-header">
          <div>
            <div className="panel-title">{title}</div>
            {subtitle && <div className="card-description">{subtitle}</div>}
          </div>
          <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close">
            <Icon name="close" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

/** Side panel for editing an item without leaving the page. */
export function Drawer({ title, subtitle, onClose, footer, children }: OverlayProps) {
  useEscape(onClose);
  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true">
        <div className="drawer-header">
          <div>
            <div className="panel-title">{title}</div>
            {subtitle && <div className="card-description">{subtitle}</div>}
          </div>
          <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close">
            <Icon name="close" />
          </button>
        </div>
        <div className="drawer-body">{children}</div>
        {footer && <div className="drawer-footer">{footer}</div>}
      </aside>
    </div>
  );
}
