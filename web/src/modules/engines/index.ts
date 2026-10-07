import { createElement } from 'react';
import { registerPage } from '@/core/navigation';
import { EnginePresets } from './EnginePresets';

registerPage({ id: 'embedding', group: 'Models', label: 'Embedding', icon: 'embedding', order: 1, component: () => createElement(EnginePresets, { kind: 'embedding' }) });
registerPage({ id: 'inference', group: 'Models', label: 'Inference', icon: 'inference', order: 2, component: () => createElement(EnginePresets, { kind: 'inference' }) });
