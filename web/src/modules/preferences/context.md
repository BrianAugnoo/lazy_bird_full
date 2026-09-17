# Module Preferences — Context

## Goal
Manages global application preferences stored on the backend (`GET /preferences/` and `PUT /preferences/`), specifically the `auto-embedding` toggle (`enable: boolean`).

## Public API Exposed
- Component: `Preferences` (React.FC)

## Dependencies
- Consumes `src/api/endpoints/preferences.ts` (`getPreferences`, `updatePreferences`)
- Consumes `src/core/types/api.ts` (`PreferencesPayload`)

## How to Extend
To add new configuration settings:
1. Add the corresponding schema fields to `PreferencesPayload` in `src/core/types/api.ts`.
2. Add the corresponding UI section and input control in `Preferences.tsx`.
3. The component uses optimistic updates and updates the backend JSON mapping on change.

## Known Limitations / TODO
- Currently only `auto-embedding` is stored in `preference.yaml`. Future plugin configurations can be appended here.
