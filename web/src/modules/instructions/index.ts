import { registerPage } from '@/core/navigation';
import { InstructionsPage } from './InstructionsPage';

registerPage({ id: 'instructions', group: 'Agents', label: 'Instructions', icon: 'instruction', order: 3, component: InstructionsPage });
