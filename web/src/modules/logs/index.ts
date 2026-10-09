import { registerPage } from '@/core/navigation';
import { LogsPage } from './LogsPage';

registerPage({ id: 'logs', group: 'System', label: 'Logs', icon: 'logs', order: 4, component: LogsPage });
