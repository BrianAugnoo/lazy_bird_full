import { registerPage } from '@/core/navigation';
import { SkillsPage } from './SkillsPage';

registerPage({ id: 'skills', group: 'Agents', label: 'Skills', icon: 'skill', order: 2, component: SkillsPage });
