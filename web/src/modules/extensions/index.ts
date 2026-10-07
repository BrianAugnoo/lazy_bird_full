import { registerPage } from '@/core/navigation';
import { ExtensionsPage } from './ExtensionsPage';
import { SchemaPage } from './SchemaPage';

registerPage({ id: 'extensions', group: 'System', label: 'Extensions', icon: 'extension', order: 5, component: ExtensionsPage });
registerPage({ id: 'schema', group: 'System', label: 'Data model', icon: 'schema', order: 6, component: SchemaPage, flush: true });
