import { createElement } from 'react';
import { registerPage } from '@/core/navigation';
import { PresetsPage } from './PresetsPage';

registerPage({ id: 'agent-presets', group: 'Agents', label: 'Agent presets', icon: 'agents', order: 4, component: () => createElement(PresetsPage, { kind: 'agent' }) });
registerPage({ id: 'session-presets', group: 'Agents', label: 'Session presets', icon: 'team', order: 5, component: () => createElement(PresetsPage, { kind: 'session' }) });
