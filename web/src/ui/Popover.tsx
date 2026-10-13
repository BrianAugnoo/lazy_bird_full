import { useEffect, useRef, type ReactNode } from 'react';

/** Anchored dialog: outside dismissal, focus containment and trigger restoration. */
export function Popover({ label, onClose, children, className = '' }: { label: string; onClose: () => void; children: ReactNode; className?: string }) {
  const root = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; });
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = root.current;
    const targets = () => [...(node?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input, [tabindex="0"]') ?? [])];
    (targets()[0] ?? node)?.focus();
    const pointer = (event: PointerEvent) => { if (!node?.contains(event.target as Node)) close.current(); };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close.current(); }
      if (event.key === 'Tab') {
        const items = targets(); const index = items.indexOf(document.activeElement as HTMLElement);
        event.preventDefault(); (items[(index + (event.shiftKey ? -1 : 1) + items.length) % items.length] ?? node)?.focus();
      }
    };
    document.addEventListener('pointerdown', pointer);
    node?.addEventListener('keydown', key);
    return () => { document.removeEventListener('pointerdown', pointer); node?.removeEventListener('keydown', key); previous?.focus(); };
  }, []);
  return <div ref={root} tabIndex={-1} role="dialog" aria-label={label} className={`popover ${className}`}>{children}</div>;
}
