/**
 * File viewers: how a stored file is shown and edited on the Files page.
 *
 * A viewer module registers itself with `registerViewer` (see
 * `modules/viewers/index.ts`); the viewer with the highest priority whose
 * `canHandle` accepts the extension is used. Text files without a dedicated
 * viewer fall back to the `text` viewer.
 */
import type { ComponentType } from 'react';
import type { FileItem } from '@/core/types/api';

export interface FileViewerProps {
  file: FileItem;
  content: string;
  /** Report edits; absent when the file cannot be edited. */
  onChange?: (content: string) => void;
}

export interface FileViewerModule {
  id: string;
  name: string;
  /** `extension` is lower case, without the dot. */
  canHandle: (extension: string) => boolean;
  Component: ComponentType<FileViewerProps>;
  /** Higher wins when several viewers accept an extension. */
  priority?: number;
}

const registry: FileViewerModule[] = [];

/** Add (or replace, by id) a viewer; returns a function removing it. */
export function registerViewer(viewer: FileViewerModule): () => void {
  const index = registry.findIndex((item) => item.id === viewer.id);
  if (index >= 0) registry[index] = viewer;
  else registry.push(viewer);
  registry.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));
  return () => {
    const position = registry.findIndex((item) => item.id === viewer.id);
    if (position >= 0) registry.splice(position, 1);
  };
}

export const normalizeExtension = (extension: string) => extension.trim().toLowerCase().replace(/^\./, '');

export function resolveViewer(extension: string): FileViewerModule | undefined {
  const clean = normalizeExtension(extension);
  return registry.find((viewer) => viewer.canHandle(clean));
}

export function getViewer(id: string): FileViewerModule | undefined {
  return registry.find((viewer) => viewer.id === id);
}

export const getAllViewers = (): readonly FileViewerModule[] => [...registry];

/** Empty the registry (tests). */
export function clearViewers(): void {
  registry.length = 0;
}
