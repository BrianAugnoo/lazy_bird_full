import type { FileItem, FileProcessing, FileState, ProcessingState } from '@/core/types/api';

export const FILE_STATES: Record<FileState, { label: string; chip: string; help: string }> = {
  ready: { label: 'Ready', chip: 'chip-success', help: 'Chunked and embedded: searchable.' },
  processing: { label: 'Processing', chip: 'chip-live', help: 'Being chunked or embedded.' },
  pending: { label: 'Waiting', chip: 'chip-outline', help: 'Not processed yet.' },
  outdated: { label: 'Outdated', chip: 'chip-warning', help: 'Changed since it was processed.' },
  new: { label: 'New', chip: 'chip-outline', help: 'Never processed.' },
  unsupported: { label: 'Not searchable', chip: 'chip-muted', help: 'No chunker handles this file type.' },
  error: { label: 'Error', chip: 'chip-error', help: 'A processing failed.' },
  missing: { label: 'Missing', chip: 'chip-error', help: 'The file is gone from the disk.' },
};

export const PROCESSING_STATES: Record<ProcessingState, { label: string; chip: string }> = {
  done: { label: 'done', chip: 'chip-success' },
  running: { label: 'running', chip: 'chip-live' },
  queued: { label: 'queued', chip: 'chip-outline' },
  paused: { label: 'paused', chip: 'chip-warning' },
  pending: { label: 'pending', chip: 'chip-outline' },
  outdated: { label: 'outdated', chip: 'chip-warning' },
  failed: { label: 'failed', chip: 'chip-error' },
  cancelled: { label: 'cancelled', chip: 'chip-muted' },
  unsupported: { label: 'unsupported', chip: 'chip-muted' },
};

export const PROCESSOR_LABELS: Record<string, string> = { chunking: 'Chunks', embedding: 'Embedding' };

export const processingLabel = (row: FileProcessing) => `${PROCESSOR_LABELS[row.processor] ?? row.processor}${row.target ? ` · ${row.target}` : ''}`;

export const fileLabel = (file: Pick<FileItem, 'name' | 'extension'>) => `${file.name}${file.extension}`;

/** Tooltip summarizing every processing of a file. */
export const processingSummary = (file: FileItem) =>
  [FILE_STATES[file.state]?.help ?? '', ...file.processing.map((row) => `${processingLabel(row)}: ${row.state}${row.error ? ` (${row.error.message})` : ''}`)]
    .filter(Boolean)
    .join('\n');
