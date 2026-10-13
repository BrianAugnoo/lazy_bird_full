# Obsidian workspace

Design created before implementation: [Figma screens, foundations and linked prototype](https://www.figma.com/design/ajGYWkwUAAGLcOMbXccnxp). Chat `3:15`, Files `3:68`, Tools `3:118`, foundations `3:165`. `design-chat.png` records the reviewed composition.

`prototype.html` is a local, offline gallery of the original designs and final interface states. `figma-state.json` records the design artifact IDs. `qa-*.png` contain reviewed fixture screenshots at desktop/mobile widths and loading/error/empty states; no personal backend data is stored in these images.

## Audit and direction

The prior interface mixed paper surfaces and cyan accents, squeezed navigation into 228px, destroyed page state on navigation, confined editing to a centered column, and provided upload-only drag and drop. Library browsing lacked consistent extension navigation and search. Chat controls and message shape lacked a clear hierarchy.

The new direction takes its chrome, alignment, density and visual restraint from [Linear's interface redesign](https://linear.app/now/how-we-redesigned-the-linear-ui). Deep black content, slightly elevated neutral navigation, quiet borders and generous content space. Chat follows the familiar right-aligned user message and bottom composer convention. No fluorescent blue, gradients, decorative illustrations or colored selection borders.

## Foundations

`web/src/styles/tokens.css` is the runtime source of truth. `tokens.json` is its portable inventory. Add semantic tokens there before using a new color; never embed colors in components. UI type uses the system sans stack; code uses the system monospace stack. Type sizes 12, 13, 14, 16, 20, 24px. Spacing scale 4, 8, 12, 16, 20, 24, 32, 48px. Control radii 6/8/12px; composer and messages 20px. Main navigation is 264px with 40px rows; contextual navigation is 280px and collapsible.

## Color and state pattern

- Primary action: ivory surface with dark text. Secondary: bordered neutral surface. Quiet action: transparent with a gray hover overlay.
- Hover: white at 6%; selection: white at 10%. Focus: visible neutral 2px outline. Disabled: reduced opacity plus disabled semantics.
- Success: sage; warning/live: amber; error/destructive: muted coral; information: lavender. Always include a label or icon: color never stands alone.
- Navy is reserved for user messages. Folder and file colors identify objects, never action or selection states.
- Loading uses a spinner and readable text; failures show the API message and Retry; empty lists describe the next useful action. Filtered lists distinguish no matches from no installed items.

## Components and icons

All action icons use Lucide, selected after searching SuperIcons, on a 24px grid, 1.8px rounded strokes, rendered at 16–20px. Custom folder silhouette follows Finder's layered folder shape using centralized neutral folder tokens. File assets live in `web/src/file_icon/`; add an SVG and one `registry.json` entry. Vite bundles the assets automatically. Extension matching is lowercase and strips the leading dot. Unknown extensions or missing registry assets show the default document. Never require a component edit to add a type.

Shared components: Icon, FileIcon, SearchInput, LibraryBrowser, Popover, Modal/Drawer, AsyncState, PageHeader. Reuse them when extending the interface. Keep forms, dialogs and row actions consistent across all pages. Component controls use native buttons, labels, details and selects where possible.

## UX conventions

Workspace tabs keep their own route, visited page trees, local drafts, scroll and live connections. Normal sidebar/profile/page-search navigation changes the focused tab without creating another tab. Returning to a visited page restores its route and state within that tab. Shift-click, Ctrl/Cmd-click and middle-click explicitly open another tab. The plus button directly duplicates the focused location, including its session, conversation or file parameters, with no picker. Ctrl/Cmd+K opens navigation search; Ctrl/Cmd+Shift+T duplicates the active tab; Alt+[ / Alt+] cycles tabs. Tabs and layout preferences persist locally; sensitive form drafts persist only while mounted, never to browser storage.

Split view (toolbar button or Ctrl/Cmd+Backslash) displays two tab views simultaneously. It reuses an existing tab; if only one exists, it duplicates the current address. Repeated split/join actions do not accumulate tabs. Clicking a pane makes it the navigation target; switching tabs replaces only that pane. The other visible tab has a subdued indicator in the shared tab strip. Drag the divider or use arrow keys to resize; double-click returns to equal widths. Small screens stack the panes. Closing split retains both tabs and all their state. Narrow panes use the same compact layout conventions as a mobile screen.

Every contextual panel can be collapsed and reopened, without clearing its state. Profile menu uses `/profile/`'s user name, with `Personal workspace` as the fallback. Users, Database and Preferences are reachable from that menu and remain registered pages.

Internal file dragging moves selected files (or one folder) to folders, parent rows and breadcrumbs. Valid targets use neutral overlays and a clear move cursor. Folder self/descendant drops are rejected. External file dragging retains the existing upload behavior. The Move action remains a keyboard-accessible alternative. A failed operation reloads the list so partially completed moves remain visible.

Overlays trap focus, restore the invoking control, support Escape and close on outside click. Search controls have accessible names. Hidden tabs cannot receive focus or handle shortcuts. Reduced-motion preferences disable animation. The interface supports 390px screens; contextual chat navigation becomes an overlay.

## Decisions and backend boundaries

- Dark is the product theme regardless of OS setting. Preferences continue to expose the backend's existing settings.
- Tabs are a frontend workspace concept: no new backend session or task contract.
- Library submenus use extensions returned by the API, with the existing default/custom conventions; instructions retain their Base instructions/Additions switch.
- Import files/folders, Create image and microphone in **chat** are visibly marked Coming soon. They never upload, create, record or request microphone permission. The existing Files page upload remains functional.
- No backend files or payload schemas are changed.

## Extension checklist

Register pages through the existing page registry. Use semantic tokens, shared components, API endpoint modules and AsyncState. Add behavior tests for new contracts and non-trivial helpers. Verify build, lint, tests, keyboard interaction, 390px layouts, loading/error/empty states, and contrast. Update `web/AGENTS.md` for architectural changes and this charter for design changes.
