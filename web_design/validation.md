# UI validation — 13 October 2026

## Passed

- `npm run build`: TypeScript project checks and production build. Application and vendor chunks split cleanly, with no bundle-size warning.
- `npm run lint`: no warnings or errors.
- `npm test`: 130 tests across 36 files. Existing API, task, streaming, search, settings, viewer and form behavior remains covered; new tests cover tab address restoration, same-tab navigation, duplication, split layout restoration, extension navigation, validated move payloads and unavailable chat controls.
- Playwright production-bundle checks: 11 browser scenarios passed. The live-backend scenario is opt-in and intentionally skipped in fixture runs.
- Read-only live backend smoke: passed independently against the running backend on port 8000; all 21 registered pages, no failed HTTP responses, console errors or runtime exceptions.
- All 21 pages at 1440px and 390px: no page or console errors, no document-width overflow.
- Empty/loading/recoverable-error states on 18 resource-backed pages, plus conversation, editor, submenu, selected, disabled and drop-target states.
- axe WCAG A/AA checks on ten primary screens: no violations, including contrast checks.
- Live conversation socket and background stream updates survive tab switching; draft content, file edits and scroll position are retained. Unsaved-tab dismissal is confirmed.
- Normal menu navigation preserves the tab count and that tab's visited-page state. Plus opens the exact current address without a picker. Two-pane view supports independent focused navigation, pointer and keyboard resizing, layout persistence, joining without discarding tabs, and responsive vertical stacking. Reopening split reuses another tab instead of accumulating duplicates. Narrow-pane controls pass the accessibility audit.
- Internal file and folder drags send the existing move payloads; target feedback, invalid descendant prevention and keyboard Move alternative are covered.
- Main and contextual panels collapse/reopen at desktop and mobile sizes. Closed mobile navigation is inert and supports Escape/outside dismissal.
- Keyboard tab navigation, navigation search, popover focus restoration and schema disclosure checked in Chromium. Reduced-motion CSS disables transitions and animations.

## Scope

No backend files, API endpoint modules or payload schemas were changed. Browser fixtures exercise the current frontend contracts and store only synthetic screenshots. The real backend smoke makes read-only requests. No real files, conversations, profiles, presets or settings were created, moved or deleted during validation.

Chat import files/folders, Create an image and microphone remain visual-only, explicitly marked Coming soon. They send no requests and request no device permissions. Existing uploads on the Files page remain available.

Re-run the production browser suite after `npm run build` with `LAZY_BIRD_PRODUCTION_QA=1 npm run test:ui`. Re-run the live check with `LAZY_BIRD_LIVE_QA=1 npx playwright test live.spec.ts`. In PowerShell set the environment variable separately using `$env:NAME='1'`.
