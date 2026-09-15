import { describe, it, expect, beforeEach } from 'vitest';
import {
  registerViewer,
  resolveViewer,
  getAllViewers,
  clearViewers,
} from './registry';
import type { FileViewerModule, FileViewerProps } from './types';

const DummyComponent = (_props: FileViewerProps) => null;

describe('FileViewer Registry (Contrat Open/Closed)', () => {
  beforeEach(() => {
    clearViewers();
  });

  it('enregistre et résout un visualiseur pour une extension donnée', () => {
    const mdViewer: FileViewerModule = {
      id: 'markdown-viewer',
      name: 'Markdown Viewer',
      canHandle: (ext) => ext === 'md' || ext === 'markdown',
      Component: DummyComponent,
    };

    registerViewer(mdViewer);
    expect(getAllViewers()).toHaveLength(1);

    // Cas nominal : extension sans point
    const found1 = resolveViewer('md');
    expect(found1?.id).toBe('markdown-viewer');

    // Cas avec point initial
    const found2 = resolveViewer('.md');
    expect(found2?.id).toBe('markdown-viewer');

    // Cas majuscule
    const found3 = resolveViewer('.MD');
    expect(found3?.id).toBe('markdown-viewer');
  });

  it('respecte la priorité d’enregistrement', () => {
    const defaultTextViewer: FileViewerModule = {
      id: 'default-text',
      name: 'Default Text',
      priority: 0,
      canHandle: (ext) => ['txt', 'md'].includes(ext),
      Component: DummyComponent,
    };

    const specializedMdViewer: FileViewerModule = {
      id: 'specialized-md',
      name: 'Specialized Markdown',
      priority: 10,
      canHandle: (ext) => ext === 'md',
      Component: DummyComponent,
    };

    registerViewer(defaultTextViewer);
    registerViewer(specializedMdViewer);

    // Pour .md, le visualiseur spécialisé doit l'emporter grâce à priority: 10
    const resolvedMd = resolveViewer('md');
    expect(resolvedMd?.id).toBe('specialized-md');

    // Pour .txt, seul le défaut répond
    const resolvedTxt = resolveViewer('txt');
    expect(resolvedTxt?.id).toBe('default-text');
  });

  it('permet le désenregistrement propre', () => {
    const jsonViewer: FileViewerModule = {
      id: 'json-viewer',
      name: 'JSON Viewer',
      canHandle: (ext) => ext === 'json',
      Component: DummyComponent,
    };

    const unregister = registerViewer(jsonViewer);
    expect(resolveViewer('json')).toBeDefined();

    unregister();
    expect(resolveViewer('json')).toBeUndefined();
    expect(getAllViewers()).toHaveLength(0);
  });

  it('retourne undefined si aucun visualiseur ne correspond', () => {
    expect(resolveViewer('unknown-ext')).toBeUndefined();
  });
});
