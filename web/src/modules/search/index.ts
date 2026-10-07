import { registerPage } from '@/core/navigation';
import { SearchPage } from './SearchPage';

registerPage({ id: 'search', group: 'Work', label: 'Search', icon: 'search', order: 2, component: SearchPage });
