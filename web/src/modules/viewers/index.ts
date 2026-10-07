import { registerViewer } from '@/core/file-viewers/registry';
import { MarkdownViewer } from './MarkdownViewer';
import { TextViewer } from './TextViewer';

const TEXT_EXTENSIONS = ['txt', 'json', 'py', 'ts', 'tsx', 'js', 'jsx', 'html', 'css', 'yaml', 'yml', 'csv', 'sh', 'log', 'ini', 'toml', 'xml', 'sql', 'rst'];

registerViewer({ id: 'markdown', name: 'Markdown', priority: 10, canHandle: (extension) => ['md', 'markdown'].includes(extension), Component: MarkdownViewer });
registerViewer({ id: 'text', name: 'Text', priority: 1, canHandle: (extension) => TEXT_EXTENSIONS.includes(extension), Component: TextViewer });
