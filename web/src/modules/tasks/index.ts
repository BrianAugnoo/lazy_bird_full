import { registerPage } from '@/core/navigation';
import { TasksPage } from './TasksPage';

registerPage({ id: 'tasks', group: 'System', label: 'Tasks', icon: 'tasks', order: 0, component: TasksPage });
