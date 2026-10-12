import { registerPage } from '@/core/navigation';
import { UsersPage } from './UsersPage';

registerPage({ id: 'users', group: 'Work', label: 'Users', icon: 'user', order: 3, component: UsersPage });
