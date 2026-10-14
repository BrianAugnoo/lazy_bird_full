import { registerPage } from '@/core/navigation';
import { DatabasesPage } from './DatabasesPage';

registerPage({ id: 'databases', group: 'System', label: 'Databases', icon: 'database', order: 1, component: DatabasesPage, sidebar: false });
