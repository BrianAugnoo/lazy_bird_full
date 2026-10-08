import { createElement } from 'react';
import { registerPage } from '@/core/navigation';
import { EnginePresets } from './EnginePresets';

registerPage({ id: 'embedding', group: 'Models', label: 'Embedding', icon: 'embedding', order: 1, component: () => createElement(EnginePresets, { kind: 'embedding' }) });
registerPage({ id: 'cross-encoder', group: 'Models', label: 'Cross-encoder', icon: 'rerank', order: 2, component: () => createElement(EnginePresets, { kind: 'cross_encoder' }) });
registerPage({ id: 'inference', group: 'Models', label: 'Inference', icon: 'inference', order: 3, component: () => createElement(EnginePresets, { kind: 'inference' }) });
