import { registerPage } from '@/core/navigation';
import { FilesPage } from './FilesPage';

registerPage({ id: 'files', group: 'Work', label: 'Files', icon: 'files', order: 1, component: FilesPage });
