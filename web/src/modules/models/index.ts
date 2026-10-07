import { registerPage } from '@/core/navigation';
import { ModelsPage } from './ModelsPage';

registerPage({ id: 'models', group: 'Models', label: 'Models', icon: 'model', order: 0, component: ModelsPage });
