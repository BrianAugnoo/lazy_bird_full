import { Bird, MessageSquare, Folder, Search, Users, Wrench, Cable, Sparkles, FileText, Layers, Network, Box, ChartNoAxesCombined, ListFilter, Activity, ListChecks, Database, KeyRound, SlidersHorizontal, Terminal, Puzzle, Workflow, Plus, X, Play, Pause, Square, RefreshCw, Trash2, Pencil, ChevronRight, ChevronDown, Menu, Check, TriangleAlert, ArrowUpRight, ArrowUp, GripVertical, Copy, Upload, Download, FolderInput, ChevronLeft, File, Info, UserRound, PanelLeftClose, Mic, Image, Command, PanelsTopLeft } from 'lucide-react';
const ICONS = {
  bird: Bird, chat: MessageSquare, files: Folder, search: Search, agents: Users,
  tool: Wrench, hook: Cable, skill: Sparkles, instruction: FileText, preset: Layers,
  team: Network, model: Box, embedding: ChartNoAxesCombined, rerank: ListFilter,
  inference: Activity, tasks: ListChecks, database: Database, key: KeyRound,
  settings: SlidersHorizontal, logs: Terminal, extension: Puzzle, schema: Workflow,
  plus: Plus, close: X, play: Play, pause: Pause, stop: Square, refresh: RefreshCw,
  trash: Trash2, edit: Pencil, chevronRight: ChevronRight, chevronDown: ChevronDown,
  menu: Menu, check: Check, alert: TriangleAlert, external: ArrowUpRight, send: ArrowUp,
  grip: GripVertical, copy: Copy, upload: Upload, download: Download, move: FolderInput,
  back: ChevronLeft, file: File, info: Info, user: UserRound, sparkles: Sparkles,
  split: PanelsTopLeft, panel: PanelLeftClose, microphone: Mic, image: Image, command: Command,
} as const;
export type IconName = keyof typeof ICONS;
/** Lucide outline family, discovered through SuperIcons. */
export function Icon({ name, size = 18, className = '', title }: { name: IconName; size?: number; className?: string; title?: string }) {
  const Component = ICONS[name];
  return <Component className={`icon ${className}`} size={size} strokeWidth={1.8} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} aria-label={title} />;
}
