/** Line icons drawn on a 24×24 grid with a 1.8 stroke. */
const PATHS = {
  bird: 'M3.5 15.5c3.5.2 6.2-1.6 7.3-5.1 1-3.2 3.7-5 6.8-4.3l2.9.7-2.6 1.4c.2 6.3-4.1 10.8-10.2 10.8-2.2 0-3.6-1.2-4.2-3.5z M16.5 8.6h.01',
  chat: 'M4 5.5h16v10.5H10l-5 4v-4H4z',
  files: 'M3.5 6.5h6l2 2h9v10.5h-17z',
  search: 'M10.5 4.5a6 6 0 1 1 0 12 6 6 0 0 1 0-12z M15 15l5 5',
  agents: 'M9 11a3.2 3.2 0 1 0 0-6.4A3.2 3.2 0 0 0 9 11z M3.5 19.5c.6-3.3 2.8-5 5.5-5s4.9 1.7 5.5 5 M16 11a2.8 2.8 0 1 0 0-5.6 M17.5 14.6c1.8.5 2.9 2.1 3.2 4.9',
  tool: 'M14.5 4.5a4 4 0 0 0-3.8 5.3L4.5 16v3.5H8l6.2-6.2a4 4 0 0 0 5.3-3.8l-2.3 2.3-3-3z',
  hook: 'M8 3.5v10a4 4 0 0 0 8 0V11 M13.5 13.5 16 11l2.5 2.5',
  skill: 'M12 3.5l2.2 5.8 5.8 2.2-5.8 2.2L12 19.5l-2.2-5.8L4 11.5l5.8-2.2z',
  instruction: 'M6.5 3.5h8l3 3v14h-11z M9.5 10.5h5 M9.5 14h5 M9.5 17.5h3',
  preset: 'M12 3.5l8.5 4.5L12 12.5 3.5 8z M3.5 12.5l8.5 4.5 8.5-4.5 M3.5 16.5l8.5 4.5 8.5-4.5',
  team: 'M7 8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z M17 8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z M12 15.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z M8.5 7.5l2 4 M15.5 7.5l-2 4 M7.5 21c.5-2.6 2.2-4 4.5-4s4 1.4 4.5 4',
  model: 'M12 3.5l8 4.5v8L12 20.5 4 16V8z M12 12l8-4 M12 12v8.5 M12 12L4 8',
  embedding: 'M5 19l5-6 4 3 5-9 M5 5v14h14',
  rerank: 'M4 6.5h16 M4 12h11 M4 17.5h6 M19 11v7 M16.5 15.5l2.5 2.5 2.5-2.5',
  inference: 'M3.5 12h4l2.5-6.5 4 13 2.5-6.5h4',
  tasks: 'M10 6.5h10 M10 12h10 M10 17.5h10 M4 6.5l1.2 1.2 2.3-2.4 M4 12l1.2 1.2 2.3-2.4 M4.5 17.5h2.5',
  database: 'M4.5 6c0-1.6 3.4-2.5 7.5-2.5s7.5.9 7.5 2.5v12c0 1.6-3.4 2.5-7.5 2.5s-7.5-.9-7.5-2.5z M4.5 6c0 1.6 3.4 2.5 7.5 2.5s7.5-.9 7.5-2.5 M4.5 12c0 1.6 3.4 2.5 7.5 2.5s7.5-.9 7.5-2.5',
  key: 'M8.5 15.5a4 4 0 1 1 3.4-6.1h8.6v3h-2v2.5h-3v-2.5h-3.6a4 4 0 0 1-3.4 3.1z M7.5 11.5h.01',
  settings: 'M4 6.5h9 M17 6.5h3 M4 12h3 M11 12h9 M4 17.5h11 M19 17.5h1 M15 4.5v4 M9 10v4 M17 15.5v4',
  logs: 'M3.5 5h17v14h-17z M7 9.5l2.5 2.5L7 14.5 M12 14.5h5',
  extension: 'M9 4.5h3.5v2a1.75 1.75 0 1 0 3.5 0v-2h3.5V9h-2a1.75 1.75 0 1 0 0 3.5h2v7H4.5v-7h2a1.75 1.75 0 1 0 0-3.5h-2V4.5z',
  schema: 'M3.5 4.5h7v5h-7z M13.5 14.5h7v5h-7z M13.5 4.5h7v5h-7z M7 9.5v7.5h6.5 M17 9.5v5',
  plus: 'M12 5v14 M5 12h14',
  close: 'M6 6l12 12 M18 6L6 18',
  play: 'M8 5.5v13l10-6.5z',
  pause: 'M8 5.5v13 M16 5.5v13',
  stop: 'M6.5 6.5h11v11h-11z',
  refresh: 'M19.5 12a7.5 7.5 0 1 1-2.2-5.3 M19.5 4.5v4h-4',
  trash: 'M4.5 6.5h15 M9.5 6.5V4h5v2.5 M6.5 6.5l1 13.5h9l1-13.5 M10.5 10.5v6 M13.5 10.5v6',
  edit: 'M15.5 4.5l4 4L9 19H5v-4z M13 7l4 4',
  chevronRight: 'M9.5 5.5l6.5 6.5-6.5 6.5',
  chevronDown: 'M5.5 9.5l6.5 6.5 6.5-6.5',
  menu: 'M4 6.5h16 M4 12h16 M4 17.5h16',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  alert: 'M12 4l9 15.5H3z M12 10v4 M12 17h.01',
  external: 'M13.5 4.5h6v6 M19.5 4.5l-8 8 M17.5 14v5.5h-13v-13H10',
  send: 'M4 12l16-7.5L13 20l-2-6z M11 14l9-9.5',
  grip: 'M9 6h.01 M15 6h.01 M9 12h.01 M15 12h.01 M9 18h.01 M15 18h.01',
  copy: 'M8.5 8.5h11v11h-11z M5.5 15.5h-1v-11h11v1',
  upload: 'M12 15V4.5 M7.5 9 12 4.5 16.5 9 M4.5 15.5v4h15v-4',
  download: 'M12 4.5V15 M7.5 10.5 12 15l4.5-4.5 M4.5 15.5v4h15v-4',
  move: 'M3.5 6.5h6l2 2h9v10.5h-17z M9.5 13.5h6 M13 11l2.5 2.5L13 16',
  back: 'M14.5 5.5 8 12l6.5 6.5',
  file: 'M6.5 3.5h7l4 4v13h-11z M13.5 3.5v4h4',
  info: 'M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17z M12 11v5.5 M12 7.5h.01',
  user: 'M12 11.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M5 20c.6-4 3.1-6 7-6s6.4 2 7 6',
  sparkles:'M12 4l1.5 4.5L18 10l-4.5 1.5L12 16l-1.5-4.5L6 10l4.5-1.5z M18.5 15.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z',
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, className = '', title }: { name: IconName; size?: number; className?: string; title?: string }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title && <title>{title}</title>}
      <path d={PATHS[name]} />
    </svg>
  );
}
