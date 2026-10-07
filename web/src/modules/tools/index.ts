import { createElement } from 'react';
import { registerPage } from '@/core/navigation';
import { CallablesPage } from './CallablesPage';

registerPage({ id: 'tools', group: 'Agents', label: 'Tools', icon: 'tool', order: 0, component: () => createElement(CallablesPage, { kind: 'tools' }) });
registerPage({ id: 'hooks', group: 'Agents', label: 'Hooks', icon: 'hook', order: 1, component: () => createElement(CallablesPage, { kind: 'hooks' }) });
