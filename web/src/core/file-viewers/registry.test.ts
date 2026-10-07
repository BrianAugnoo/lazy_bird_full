import { beforeEach, describe, expect, it } from 'vitest';
import { clearViewers, getAllViewers, registerViewer, resolveViewer, type FileViewerModule } from './registry';

const Dummy = () => null;
const viewer = (id: string, extensions: string[], priority = 0): FileViewerModule => ({
  id,
  name: id,
  canHandle: (extension) => extensions.includes(extension),
  Component: Dummy,
  priority,
});

describe('file viewer registry', () => {
  beforeEach(clearViewers);

  it('resolves a viewer whatever the case or dot of the extension', () => {
    registerViewer(viewer('markdown', ['md']));
    expect(resolveViewer('.MD')?.id).toBe('markdown');
    expect(resolveViewer('md')?.id).toBe('markdown');
    expect(resolveViewer('pdf')).toBeUndefined();
  });

  it('prefers the highest priority', () => {
    registerViewer(viewer('text', ['md', 'txt'], 1));
    registerViewer(viewer('markdown', ['md'], 10));
    expect(resolveViewer('md')?.id).toBe('markdown');
    expect(resolveViewer('txt')?.id).toBe('text');
  });

  it('replaces a viewer with the same id and can unregister it', () => {
    registerViewer(viewer('text', ['txt']));
    const remove = registerViewer(viewer('text', ['log']));
    expect(getAllViewers()).toHaveLength(1);
    expect(resolveViewer('log')?.id).toBe('text');
    remove();
    expect(getAllViewers()).toHaveLength(0);
  });
});
