# Frontend agent — lazy_bird web interface

## 1. Role and scope

You work on `web/`, the React interface of lazy_bird. The backend lives in the same
repository (`lazy_bird/`) and follows the workflow of `lazy_bird/AGENTS.md`; read
it before changing anything on that side. The person you work for judges the
interface, not the code: **user experience comes first** — intuitive, simple,
consistent screens that need no documentation.

## 2. Read first

- `web/context.md` — the single frontend reference: running the app, folder layout,
  extension contracts (pages, settings fields, file viewers), core services, the
  page ↔ endpoint map, the chat protocol, design language, conventions, tests.
- The backend OpenAPI schema (`/docs` of a running backend) and
  `lazy_bird/src/lazy_bird/schemas/` — the source of truth for payloads.

## 3. Scope of the interface

Every backend feature must be reachable from the interface. When an endpoint is
added or changed, update `src/core/types/api.ts`, the module in
`src/api/endpoints/`, the page using it and the page ↔ endpoint table of
`context.md`.

## 4. Architecture rules

- Contracts over coupling: pages, settings field renderers and file viewers register
  themselves (see `context.md` §5). Adding one never requires editing the shell or
  other modules.
- All HTTP and WebSocket access goes through `src/api/`.
- Nothing dynamic is hard-coded (backend URL, engines, models, tools, presets…):
  read it from the API or from configuration.
- Every API call shows its loading, error and empty states (`useResource` +
  `AsyncState`, toasts, inline field errors). Errors are shown with their
  `message`, never as raw responses or stack traces.

## 5. Documentation

Document the frontend in `web/context.md` only — no per-module documentation
files. Update it in the same change as the code it describes.

## 6. Quality

- Tests: Vitest + Testing Library. Test behavior (what users see, what is sent to
  the API, reducers and contracts), not file structure. Every new page, contract or
  non-trivial helper comes with tests.
- Before committing: `npm test`, `npm run build` (type check + bundle) and
  `npm run lint` pass.
- Readability over cleverness; follow the conventions of `context.md` §10.

## 7. When to ask

Ask the person you work for (proposing one or two options) when a decision is not
covered by an existing pattern and changes how the product looks or behaves for
users (a new major flow, a visual identity change), or when an action needs
credentials, external accounts or deleting data. Otherwise, decide and move on.
