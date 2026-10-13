# Agent guide — lazy_bird web interface

Everything needed to work on `web/`, the React interface of lazy_bird: how to work
(§1–6) and the reference of the frontend (§7–18). This file is the only frontend
documentation: update it in the same change as the code it describes. The backend
and the repository workflow are documented in `lazy_bird/AGENTS.md`.

## 1. Role and scope

You work on `web/`. The backend lives in the same repository (`lazy_bird/`) and
follows the workflow of `lazy_bird/AGENTS.md`; read it before changing anything on
that side. The person you work for judges the interface, not the code: **user
experience comes first** — intuitive, simple, consistent screens that need no
documentation.

## 2. Read first

- `lazy_bird/AGENTS.md` — the repository workflow (steps, commits, validation) and
  the backend: extension contracts, data model, task system, agentic loop.
- §9 — where the API payloads are defined and how errors look.

## 3. Scope of the interface

Every backend feature must be reachable from the interface. When an endpoint is
added or changed, update `src/core/types/api.ts`, the module in
`src/api/endpoints/`, the page using it and the page ↔ endpoint table (§13).

## 4. Architecture rules

- Contracts over coupling: pages, settings field renderers and file viewers register
  themselves (§11). Adding one never requires editing the shell or other modules.
- All HTTP and WebSocket access goes through `src/api/`.
- Nothing dynamic is hard-coded (backend URL, engines, models, tools, presets…):
  read it from the API or from configuration.
- Every API call shows its loading, error and empty states (`useResource` +
  `AsyncState`, toasts, inline field errors). Errors are shown with their
  `message`, never as raw responses or stack traces.

## 5. Quality

- Tests: Vitest + Testing Library. Test behavior (what users see, what is sent to
  the API, reducers and contracts), not file structure. Every new page, contract or
  non-trivial helper comes with tests (§17).
- Before committing: `npm test`, `npm run build` (type check + bundle) and
  `npm run lint` pass.
- Readability over cleverness; follow the conventions of §16.
- No per-module documentation files: document here.

## 6. When to ask

Ask the person you work for (proposing one or two options) when a decision is not
covered by an existing pattern and changes how the product looks or behaves for
users (a new major flow, a visual identity change), or when an action needs
credentials, external accounts or deleting data. Otherwise, decide and move on.

## 7. What it is

A single-page React app that controls the whole lazy_bird backend: chatting with
agent sessions, files, search, the extension library (tools, hooks, skills,
instructions, presets), models and engines, background tasks, databases, keys,
preferences, logs and extensions. The person using it does not code: **every
screen must be understandable without reading documentation**. Prefer one obvious
action per screen, plain words over jargon, and explain consequences before
destructive actions.

Stack: React 19, TypeScript 6, Vite 8, Vitest + Testing Library (jsdom), Oxlint.
No UI framework and no router library: the few building blocks needed live in
`src/ui/` and `src/core/`.

## 8. Running it

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to the backend
npm test           # vitest
npm run build      # tsc -b && vite build
npm run lint       # oxlint
```

- In development the app calls `/api/...`; Vite proxies it (HTTP and WebSockets) to
  `http://localhost:8000`, or to `$LAZY_BIRD_API` when set.
- A production build calls `VITE_API_URL` when set, else `http://localhost:8000`.
- Start the backend with `uv run uvicorn lazy_bird.main:app --reload` from `lazy_bird/`.

## 9. Source of truth for the API

The backend is in the same repository (`lazy_bird/`). Its OpenAPI schema (`/docs`,
`/openapi.json`) and `lazy_bird/src/lazy_bird/schemas/` define every payload;
`src/core/types/api.ts` mirrors them by hand. When a backend schema changes, update
`api.ts` and the endpoint module in the same commit.

Every backend error has the shape `{"error": {"code", "message", "details"}}`; the
client turns it into an `ApiError` (`status`, `code`, `message`, `details`,
`fieldErrors` = `details.fields`). Never show a stack trace or a raw response:
show `message` (toasts, inline alerts) and put `fieldErrors` next to their fields.
Timestamps arrive in UTC with an explicit offset.

## 10. Folder layout

```
src/
  main.tsx, App.tsx      entry point and shell (sidebar + current page)
  index.css              imports the style sheets below
  styles/                tokens.css (colors, type, radii; light + dark),
                         base.css, components.css (buttons, chips, forms, lists,
                         tables, modals, drawers, toasts…), layout.css (shell),
                         pages.css (styles specific to pages), workspace.css
                         (Obsidian chrome and shared interaction conventions)
  api/
    client.ts            request(), ApiError, toApiError, downloads, uploadBody() (progress)
    socket.ts            socketUrl(), LiveSocket (reconnecting JSON WebSocket)
    endpoints/           one typed module per backend area (see §13)
  core/
    navigation.ts        page registry (contract, §11.1)
    router.ts            hash router: #/{page}?key=value
    useResource.ts       load data with loading / error / reload
    tasks/store.ts       live task queue over /ws/tasks, file change events
    fields/              settings field contract (§11.2)
    file-viewers/        file viewer contract (§11.3)
    types/api.ts         backend payload types
  file_icon/             SVG assets + registry.json; extension lookup with fallback
  ui/                    shared components: Icon, FileIcon, SearchInput,
                         LibraryBrowser, Popover, PageHeader, AsyncState, Modal,
                         Drawer, MultiSelect, ChoiceList, KeyValueEditor, Markdown,
                         Toasts, Dialogs (styled confirm/prompt), Sidebar
  modules/               one folder per feature; an index.ts registers its pages
  test/http.ts           mockApi(): fetch mock keyed by "METHOD /path"
  test/callables.ts      callable(): a tool or hook as the API lists it
```

## 11. Contracts (extension points)

Nothing in the shell knows the pages, fields or viewers: each registers itself.

### 11.1 Pages — `core/navigation.ts`

A module `src/modules/{name}/index.ts` calls `registerPage(...)`. `App.tsx` imports
every `modules/*/index.ts` with `import.meta.glob(..., { eager: true })`, so adding a
folder adds its page; nothing else to edit.

```ts
registerPage({
  id: 'tasks',            // address: #/tasks
  group: 'System',        // sidebar group: Work | Agents | Models | System
  label: 'Tasks',
  icon: 'tasks',          // a name from ui/Icon.tsx
  order: 0,               // position inside the group
  component: TasksPage,
  flush: false,           // true: full-bleed, the page handles its scrolling (chat)
});
```

Pages keep their state in the address when it should survive a reload or be
linkable (`useRoute()`, `setParams({...})`, `navigate(page, params)`), e.g.
`#/chat?session=1&conversation=3`, `#/files?dir=docs&file=12`,
`#/instructions?kind=sub`.

### 11.2 Settings fields — `core/fields/`

Engines, presets, tools, hooks, databases and preferences describe their settings
with a `kwargs_key` map (built by the backend from a pydantic `*Settings` model).
`modules/settings-form/SettingsForm.tsx` renders it; each attribute descriptor is:

| key | meaning |
| --- | --- |
| `default_field` | `true`: `content` names a renderer `"{extension}.{file}.{function}"`; `false`: `content` is an HTML snippet |
| `content`, `args` | renderer name (or HTML) and its arguments |
| `type`, `required`, `nullable`, `default`, `title`, `description` | metadata of the attribute |

Renderers live in `src/modules/fields/{extension}/{file}.ts` (loaded lazily by
`core/fields/loader.ts`) and are plain DOM functions:
`(container, { name, value, descriptor, args, onChange, api }) => cleanup?`.
`onChange(undefined)` removes the value so the default applies. Built-in renderers:
`default.basic.{text,textarea,integer,number,checkbox,select,password,list,json,reference,email,url}`.
HTML snippets may mark their input with `data-field-input`, else the first
input/select/textarea is used (see `core/fields/html.ts`).

### 11.3 File viewers — `core/file-viewers/registry.ts`

```ts
registerViewer({ id, name, canHandle: (extension) => boolean, Component, priority });
```

`Component` receives `{ file, content, onChange? }` (no `onChange` = read only).
The Files page handles loading, saving (Ctrl+S), unsaved changes and downloads.
Text files without a dedicated viewer use the `text` viewer; binary files get a
download prompt. Built-in viewers: `modules/viewers/` (markdown with write / side
by side / preview, text).

## 12. Core services

- **`useResource(loader, deps)`** → `{ data, error, loading, reload, setData }`.
  Render it with `<AsyncState {...resource} onRetry={resource.reload} empty={...}>`,
  which shows loading, error (with retry) and empty states: every list needs all three.
- **Toasts** (`useToast()` from `ui/toastContext`): `show(message)` after a
  successful action, `error(reason)` for failures that have no better place.
- **Dialogs** (`useDialogs()` from `ui/dialogContext`): `confirm({title, message,
  danger})` before destructive actions, `prompt({title, label, initial, options})`
  for one value. Never use `window.confirm` / `window.prompt`.
- **Task store** (`core/tasks/store.ts`): one `/ws/tasks` connection shared by the
  app. `useTaskStore()` gives `{tasks, kinds, resources, waiting, unresponsive, status}` (tasks in
  queue order: running, waiting by priority (lowest number first, 5 by default) and position, finished). `taskAction()` (pause, resume, cancel, retry, delete and `run_now` = priority 0),
  `moveTask()`, `setTaskPriority()` send commands over the socket (HTTP fallback). `unresponsive`
  lists the running tasks that were asked to make room for a more urgent one and have not stopped yet.
  `onFileChange(listener)` is called with a file id whenever one of its processings
  changes (the backend sends `{"type": "file", "file_id"}` on the same socket).
- **Conversation socket** (`modules/chat/useConversation.ts`): see §14.

## 13. Pages and the endpoints they use

| Page (`#/id`) | Module | Backend |
| --- | --- | --- |
| Chat (`chat`) | `modules/chat` | `/sessions/*` (incl. `from-preset`), `/agents/*` (incl. `from-preset`, `/{id}/tools`), `/conversations/*` (incl. `rewind`, `stop`), `/messages/*`, `WS /ws/conversations/{id}`, `/session-presets/`, `/agent-presets/`, tools/hooks/skills/instructions lists, inference presets/engines |
| Files (`files`) | `modules/files` | `/files/*` (upload, directories, directory CRUD, content, full, download, process, processing, scan, all), `/files/{id}/chunks`, file events of `/ws/tasks` |
| Users (`users`) | `modules/users` | `/users/*` and `/profile/` (list, create, partial update, delete; the active user is marked and any other can be made active; edited in a drawer: languages are an ordered list moved with arrows; the backend's `meta` is not shown or sent) |
| Search (`search`) | `modules/search` | `POST /search/` (embedding only, or reranking with `rerank`, `cross_encoder_preset_id`, `top_n`), embedding and cross-encoder presets, files |
| Tools, Hooks (`tools`, `hooks`) | `modules/tools` | `/tools/*`, `/hooks/*` (list, reload, settings per module file). A side menu lists the extensions (`default`, `custom` — both always shown — then the others; the chosen one is `?extension=`), and each module (Python file) of the chosen extension is a section with its items, their description (a hook's whole docstring), parameters, session values and the module's settings |
| Skills (`skills`) | `modules/skills` | `/skills/*` (incl. resource files) |
| Instructions (`instructions`) | `modules/instructions` | `/instructions/{full|sub}/*` |
| Agent / session presets | `modules/presets` | `/agent-presets/*`, `/session-presets/*`, tools/hooks lists (picker, §15) |
| Models (`models`) | `modules/models` | `/models/*` (download with file choice, upload from the computer with progress, sync, hub status/login/files), model tasks |
| Embedding, Cross-encoder (`cross-encoder`), Inference | `modules/engines` | `/{kind}-engines/`, `/{kind}-presets/*` (kind `embedding`, `cross-encoder`, `inference`), `POST /inference/complete`; engines with `local: true` show that they run the model on this computer |
| Tasks (`tasks`) | `modules/tasks` | `WS /ws/tasks` (snapshot, events, commands incl. `update` with `priority: 0` = Run now; `resources.models` lists the local models in memory: idle or in use, own process, real memory; `resources.processes` marks running isolated tasks with their memory), `DELETE /tasks/finished` |
| Databases (`databases`) | `modules/databases` | `/databases/*`, `/databases/vector/tables/*` |
| API keys (`api-keys`) | `modules/api-keys` | `/api-keys/*` |
| Preferences (`preferences`) | `modules/preferences` | `GET/PATCH /preferences/`, `/preferences/form` |
| Logs (`logs`) | `modules/logs` | `/logs/`, `/logs/trace`, `/logs/tracing` |
| Extensions, Data model | `modules/extensions` | `/extensions/failures`, `/extensions/reload`, `/schemas` (iframe) |

The sidebar shows the server state (`GET /health`, every 15 s) and running tasks.
`GET /tasks/` reloads the queue order after a `reordered` event and the per-task
REST commands replace the socket while it is down. Single-item reads (`GET
/agents/{id}`, `/sessions/{id}`, `/tasks/{id}`, `/messages/{id}`…) and the
non-streaming chat calls (`POST /conversations/{id}/messages`, `/run`,
`/sessions/{id}/chat`) are typed in `api/endpoints/` for future screens; the chat
streams over the WebSocket instead.

### Search modes

The Search page has two tabs. **Embedding only** (default) sends `query`, `top_k`
(Results, default 8), the embedding preset and the file filter. **Reranking** shows,
in Options (opened when the tab is chosen): embedding preset, cross-encoder preset,
Embedding candidates (`top_n`, default 50) and Final results (`top_k`, default 10),
and sends `rerank: true` with them. `top_n` is the candidate pool read by the
cross-encoder, `top_k` the final count, and `top_n > top_k` is required: the page
shows the error under the field and disables Search (`candidatesError` in
`modules/search/searchRequest.ts`, which also builds the payload), and still shows
the backend's `fields.top_n` error if the server rejects it. Reranked results show
their cross-encoder `score` next to the embedding `distance`. Without a
cross-encoder preset the page links to the Cross-encoder page instead of searching.

## 14. Chat

Layout (`ChatPage`): a rail (session picker, agents as a tree — masters first, then
their sub-agents — each with its conversations) and the conversation. The address
holds `session`, `conversation` and, for a new chat, `agent`.

`useConversation(id)` opens `/ws/conversations/{id}` and feeds `chatReducer`
(`modules/chat/state.ts`, pure and unit-tested):

| server event | effect |
| --- | --- |
| `conversation` | full state (sent on connection and reconnection) |
| `message` | stored message added/replaced; ends the streamed text it replaces |
| `token`, `reasoning` | streamed answer / reasoning |
| `tool_start` | the tool running now |
| `status` | `generating`, `retrying` (attempt, delay, reason), `waiting_resources`, `running_hooks`, `delegating` |
| `delegation` | activity of a sub-agent (`agent_id`, `conversation_id`, nested `event`) |
| `done` | end of the run (`completed`, `stopped`, `error`) |
| `error` | problem with a command (e.g. `conversation_busy`) |

Commands: `{"type": "message", "content"}`, `{"type": "run"}` (answer now / retry),
`{"type": "stop"}`. Messages are grouped by `toBlocks()`: tool responses attach to
their call (matched by `tool_call_id`); a tool response's `meta.delegation`
(`agent_id`, `agent`, `conversation_id`) links to the sub-agent's conversation.
Errors are stored messages (`role: "error"`, `meta.code`) shown with a Retry button.
Editing a prompt = `PATCH /messages/{id}` + `rewind` + `run`; regenerating =
`rewind` to the previous prompt + `run`.

## 15. Design language

"Obsidian workspace": deep black content, neutral elevated surfaces, gray
translucent hover/selection overlays and ivory primary buttons. Dark regardless of
the OS theme. No cyan secondary accent. Sage means success, amber warning/live,
coral error/destructive, lavender information; navy is reserved for user messages.
Status color always comes with text or an icon. Use `styles/tokens.css`, never raw
colors. `workspace.css` applies the shared design to every registered page.
Hairline borders, 6/8/12px control radii, 20px message/composer radii, no gradients,
sentence case everywhere. The design charter, portable tokens, Figma prototype and
reviewed screenshots live in `../web_design/` (explicitly requested design knowledge
base; implementation reference remains here). Lists are `.list` / `.list-row`, editing happens in a
`Drawer`, confirmations in `Dialogs`, results in toasts. A dialog offering options
(`ChoiceList`) never acts on a single click: the user picks, then confirms with the
primary button or Enter. Overlays trap focus, restore their invoking control, and
Escape closes only the overlay opened last. The tools and
hooks of an agent or agent preset are chosen in a picker (`modules/tools/CallableField`
opens `CallablePicker`), laid out like the Tools and Hooks pages: extensions on the
left, modules as sections, a checkbox per item, per module and per extension (dashed
when partly chosen); Confirm applies the choice to the form, which keeps the order
items were chosen in (hooks run in that order). Tools expose a native `details`
disclosure containing the full JSON schema, separate from their parameter summary.
Instructions, agent presets and session presets have searchable extension submenus,
with default/custom always present; instruction kinds retain their own tabs.
Icons come from `ui/Icon.tsx` (Lucide 24×24 line icons with 1.8px rounded strokes,
selected through SuperIcons). File icons use `file_icon/registry.json`: add an SVG
and one extension mapping; unknown or missing mappings resolve to document.svg.
Folder icons use a Finder-inspired silhouette with the centralized folder tokens.
Layouts must work from 390 px wide (the chat rail becomes an overlay).

## 16. Conventions

- Components in `PascalCase.tsx`; helpers in separate `.ts` files (fast refresh
  needs component files to export only components).
- Text shown to users is English, short and concrete ("Delete 3 files?", not
  "Are you sure?"). Name things the way users think of them (e.g. "Base
  instructions" / "Additions" for full / sub instructions).
- No hard-coded backend lists (engines, models, tools…): always fetch them.
- No `console.log` for errors: show them.

## 17. Tests

`npm test` runs Vitest (jsdom). Test behavior, not structure: reducers and helpers
(`chat/state`, `tasks/store`, router, key/value parsing, paths), contracts (field
loader, viewer registry) and components through what the user sees and what is sent
to the API (`mockApi` from `src/test/http.ts`). Every new page or contract change
comes with tests.

## 18. Known limitations

- `api.ts` types are maintained by hand (no generation from OpenAPI yet).
- Tool and hook settings are sent and shown in clear text, including secrets
  (password fields only hide them on screen).
- The Data model page loads Mermaid from a CDN (needs internet access).
- Chat file/folder import, image creation and microphone are Coming soon UI only:
  no requests, recording or browser permission prompts. Files-page upload works.

## 19. Workspace tabs and layout

The shell keeps a mounted page tree for every page visited within a workspace tab.
Inactive tabs and inactive page views use `hidden` and `inert`; they retain drafts,
scroll and live sockets. Do not use React
Activity or unmount inactive trees: suspending effects would disconnect live chats.
`core/workspace.ts` restores only tab IDs and routes from sessionStorage, validates
them against the page registry, and ignores malformed/obsolete entries. No form
drafts, credentials or file contents are persisted. Split pane IDs and their size
ratio are restored with validated tab addresses. The main sidebar's collapsed
state is stored in localStorage.

`RouteContext` scopes `useRoute()` and `useRouteActions().setParams` to each tree.
Pages must use the scoped action hook, never the global `setParams`, so background
loads cannot change another tab's address. The active tab mirrors its route into
the existing hash address; hash links remain supported. Normal sidebar, profile
menu and page-search navigation always changes the focused tab; returning to a
visited page restores that tab's own route and mounted state. Navigation never
creates or switches to another tab automatically. Ctrl/Cmd/Shift-click and
middle-click explicitly open additional tabs. Plus duplicates the focused tab's
complete current address directly, without a page picker. Ctrl/Cmd+K searches pages,
Ctrl/Cmd+Shift+T duplicates
the active address, Alt+[ / Alt+] switches tabs. Tablist supports arrows, Home/End
and Delete. Draft chat/file tabs require confirmation before closing. Keyboard
handlers inside a page must check `useRouteActions().active`. `updateTabParams`
also scopes writes to the originating page, so background chat initialization cannot
replace the tab's current Files view.

The split-view button (Ctrl/Cmd+Backslash) displays the focused tab alongside another
open tab, reusing an existing tab to avoid clutter. If only one tab exists, it
duplicates the current address. Both panes are visible; pointer/focus selects the navigation target without
reparenting or remounting either tree. The shared tab strip distinguishes the
focused tab and the other visible pane. Selecting a hidden tab replaces the focused
pane only. `SplitDivider` resizes from 25–75% with pointer dragging or arrow keys;
double-click resets 50/50. On screens below 700px the panes stack vertically and
the divider uses Up/Down. Closing split retains both tabs and their state; closing
a visible tab collapses the split and focuses the surviving pane. Each pane's
content uses container queries; narrow chat panes collapse contextual navigation
and expose its existing reopen button.

The sidebar is 264px with 40px entries; its footer reads the name from `/profile/`,
falling back to Personal workspace, and opens an anchored Users/Database/Preferences
dialog. User changes emit `profile-changed`; sidebar profile reloads on this event
and window focus. Chat and library sidebars have explicit collapse/reopen controls.
The editor consumes the full content width and available height.

Internal file-manager drag payloads use `application/x-lazy-bird-files`, validated
by `modules/files/drag.ts`. Selected files move using the existing `{dir}` PATCH;
folders use the existing directory-move endpoint. Folders, parent rows and
breadcrumbs are drop targets; folder self/descendant/unchanged-parent moves are
rejected. Failure reloads the catalog after any partial move. External drops still
upload; Move… provides the keyboard alternative.

Validation: `npm test` for behavioral/unit contracts, `npm run build` for types and
production output, `npm run lint`, and `npm run test:ui` for Playwright browser
checks. Install Chromium once with `npx playwright install chromium`. Browser tests
mock only HTTP/WS API surfaces, verify mounted tabs/live sockets, move payloads,
overlays, schema/search and all 21 pages at 1440/390px; axe checks WCAG A/AA contrast
and controls on primary screens. `LAZY_BIRD_LIVE_QA=1 npx playwright test live.spec.ts`
runs an optional read-only smoke against the configured running backend. Do not
mutate the real backend during UI QA. Playwright results are ignored; reviewed
fixture screenshots are saved in `web_design/`.

Build splits shared third-party code into a vendor chunk. Set
`LAZY_BIRD_PRODUCTION_QA=1` before `npm run test:ui` to test the built bundle through
Vite preview on port 4173 (run the build first). Both production and development
fixtures intercept only API URLs, never frontend source modules.
