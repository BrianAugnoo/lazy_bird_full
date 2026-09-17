import { registerViewer } from '@/core/file-viewers/registry';
import { MarkdownViewer } from './markdown/MarkdownViewer';
import { TextCodeViewer } from './text-code/TextCodeViewer';
import { MetadataViewer } from './metadata/MetadataViewer';
import { UnsupportedViewerModal } from './UnsupportedViewerModal';

let isRegistered = false;

export function registerAllBuiltinViewers(): void {
  if (isRegistered) return;

  // 1. Markdown Viewer & Editor (high priority)
  registerViewer({
    id: 'markdown-viewer',
    name: 'Markdown Editor & Viewer',
    icon: '📝',
    priority: 10,
    canHandle: (ext) => ['md', 'markdown'].includes(ext.toLowerCase()),
    Component: MarkdownViewer,
  });

  // 2. Code & Text Editor
  const codeExtensions = [
    'txt', 'json', 'py', 'ts', 'tsx', 'js', 'jsx', 'html', 'css',
    'yaml', 'yml', 'csv', 'sh', 'bash', 'log', 'ini', 'toml', 'env', 'xml', 'sql'
  ];
  registerViewer({
    id: 'text-code-viewer',
    name: 'Code & Text Editor',
    icon: '📄',
    priority: 5,
    canHandle: (ext) => codeExtensions.includes(ext.toLowerCase()),
    Component: TextCodeViewer,
  });

  isRegistered = true;
}

export { MarkdownViewer, TextCodeViewer, MetadataViewer, UnsupportedViewerModal };
export { FileViewerModal } from './FileViewerModal';
