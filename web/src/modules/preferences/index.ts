import { registerPage } from '@/core/navigation';
import { PreferencesPage } from './PreferencesPage';

registerPage({ id: 'preferences', group: 'System', label: 'Preferences', icon: 'settings', order: 3, component: PreferencesPage });
