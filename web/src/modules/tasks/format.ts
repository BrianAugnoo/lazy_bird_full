import type { LoadedModel } from '@/core/types/api';

/** `1m 5s` between two ISO dates (until now when `end` is null). */
export function duration(start: string | null, end: string | null): string {
  if (!start) return '';
  const seconds = Math.max(0, ((end ? new Date(end) : new Date()).getTime() - new Date(start).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

const RESOURCE_LABELS: Record<string, { label: string; unit?: string; scale?: number }> = {
  cpu: { label: 'Worker slots' },
  vram_mb: { label: 'GPU memory', unit: 'GB', scale: 1024 },
  ram_mb: { label: 'Memory', unit: 'GB', scale: 1024 },
};

/** How a resource is called on screen (`vram_mb` -> "GPU memory"). */
export function resourceLabel(name: string): string {
  return RESOURCE_LABELS[name]?.label ?? name;
}

/** An amount of a resource as shown on screen (megabytes as GB). */
export function amount(name: string, value: number): string {
  const spec = RESOURCE_LABELS[name];
  if (spec?.scale) return `${(value / spec.scale).toFixed(1)} ${spec.unit}`;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** What a loaded model reserves, and what its process really uses when it has one. */
export function modelMemory(model: LoadedModel): string {
  const reserved = Object.entries(model.needs)
    .map(([name, value]) => `${amount(name, value)} ${name === 'vram_mb' ? 'of GPU memory' : 'of memory'}`)
    .join(', ');
  const really = model.memory
    ? ` (really using ${(model.memory.rss_mb / 1024).toFixed(1)} GB memory${model.memory.vram_mb ? `, ${(model.memory.vram_mb / 1024).toFixed(1)} GB GPU` : ''})`
    : '';
  return reserved + really;
}
