import { registerViewer } from '@/core/file-viewers/registry';
import { MarkdownViewer } from './markdown/MarkdownViewer';
import { TextCodeViewer } from './text-code/TextCodeViewer';
import { MetadataViewer } from './metadata/MetadataViewer';

let isRegistered = false;

export function registerAllBuiltinViewers(): void {
  if (isRegistered) return;

  // 1. Visualiseur Markdown (haute priorité)
  registerViewer({
    id: 'markdown-viewer',
    name: 'Éditeur & Visualiseur Markdown',
    icon: '📝',
    priority: 10,
    canHandle: (ext) => ['md', 'markdown'].includes(ext.toLowerCase()),
    Component: MarkdownViewer,
  });

  // 2. Visualiseur Code & Texte
  const codeExtensions = [
    'txt', 'json', 'py', 'ts', 'tsx', 'js', 'jsx', 'html', 'css',
    'yaml', 'yml', 'csv', 'sh', 'bash', 'log', 'ini', 'toml', 'env', 'xml'
  ];
  registerViewer({
    id: 'text-code-viewer',
    name: 'Éditeur Code & Texte',
    icon: '📄',
    priority: 5,
    canHandle: (ext) => codeExtensions.includes(ext.toLowerCase()),
    Component: TextCodeViewer,
  });

  // 3. Fallback universel (métadonnées)
  registerViewer({
    id: 'metadata-fallback',
    name: 'Inspecteur de métadonnées',
    icon: '📁',
    priority: -100,
    canHandle: () => true, // capture toutes les autres extensions
    Component: MetadataViewer,
  });

  isRegistered = true;
}

export { MarkdownViewer, TextCodeViewer, MetadataViewer };
export { FileViewerModal } from './FileViewerModal';
