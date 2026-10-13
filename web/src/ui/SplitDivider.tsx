import { useEffect, useState } from 'react';
import { splitRatio } from '@/core/workspace';

/** Resizable by pointer or keyboard; double click restores equal pane sizes. */
export function SplitDivider({ ratio, onChange }: { ratio: number; onChange: (ratio: number) => void }) {
  const [stacked, setStacked] = useState(() => window.matchMedia('(max-width: 700px)').matches);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 700px)');
    const update = () => setStacked(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return <div role="separator" tabIndex={0} className="split-divider" aria-label="Resize panes" aria-orientation={stacked ? 'horizontal' : 'vertical'} aria-valuemin={25} aria-valuemax={75} aria-valuenow={Math.round(ratio)}
    onDoubleClick={() => onChange(50)}
    onPointerDown={event => { if (event.button === 0) { event.preventDefault(); event.currentTarget.focus(); event.currentTarget.setPointerCapture(event.pointerId); } }}
    onPointerMove={event => {
      if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
      const bounds = event.currentTarget.parentElement!.getBoundingClientRect();
      onChange(splitRatio(100 * (stacked ? (event.clientY - bounds.top) / bounds.height : (event.clientX - bounds.left) / bounds.width)));
    }}
    onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
    onKeyDown={event => {
      const direction = stacked ? ['ArrowUp', 'ArrowDown'] : ['ArrowLeft', 'ArrowRight'];
      if (direction.includes(event.key)) { event.preventDefault(); onChange(splitRatio(ratio + (event.key === direction[0] ? -2 : 2))); }
      if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); onChange(event.key === 'Home' ? 25 : 75); }
    }} />;
}
