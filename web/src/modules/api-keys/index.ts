import { registerPage } from '@/core/navigation';
import { ApiKeysPage } from './ApiKeysPage';

registerPage({ id: 'api-keys', group: 'System', label: 'API keys', icon: 'key', order: 2, component: ApiKeysPage });
