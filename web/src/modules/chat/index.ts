import { registerPage } from '@/core/navigation';
import { ChatPage } from './ChatPage';

registerPage({ id: 'chat', group: 'Work', label: 'Chat', icon: 'chat', order: 0, component: ChatPage, flush: true });
