import { useEffect, useId, useRef, type ReactNode, type RefObject } from 'react';
import { useRouteActions } from '@/core/router';
import { Icon } from './Icon';

/** Open overlays, the last opened on top: Escape only closes that one. */
const open: object[] = [];

function useEscape(onClose: () => void, root: RefObject<HTMLElement | null>) {
  const { active } = useRouteActions();
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  });
  useEffect(() => {
    if (!active) return;
    const overlay = {};
    open.push(overlay);
    const previous = document.activeElement as HTMLElement | null;
    const node = root.current;
    const targets = () => [...(node?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]') ?? [])].filter(item => !item.closest('[hidden]'));
    const first = node?.querySelector<HTMLElement>('[autofocus]') ?? targets()[0] ?? node;
    first?.focus();
    const handler = (event: KeyboardEvent) => {
      if (open[open.length - 1] !== overlay) return;
      if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); close.current(); }
      if (event.key === 'Tab') {
        const items = targets();
        if (!items.length) { event.preventDefault(); node?.focus(); return; }
        const index = items.indexOf(document.activeElement as HTMLElement);
        if (event.shiftKey && index <= 0) { event.preventDefault(); items[items.length - 1].focus(); }
        else if (!event.shiftKey && (index === -1 || index === items.length - 1)) { event.preventDefault(); items[0].focus(); }
      }
    };
    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      open.splice(open.indexOf(overlay), 1);
      if (previous?.isConnected && !previous.closest('[hidden]')) previous.focus();
    };
  }, [active, root]);
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
  const root = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEscape(onClose, root);
  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div ref={root} tabIndex={-1} className="modal-window" style={{ maxWidth: width }} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="modal-header">
          <div>
            <div className="panel-title" id={titleId}>{title}</div>
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
  const root = useRef<HTMLElement>(null);
  const titleId = useId();
  useEscape(onClose, root);
  return (
    <div className="drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside ref={root} tabIndex={-1} className="drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="drawer-header">
          <div>
            <div className="panel-title" id={titleId}>{title}</div>
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
