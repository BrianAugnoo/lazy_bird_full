# Context Module — file-explorer

## Goal
Google Drive-style file explorer interface featuring vertical folder and file navigation, interactive breadcrumbs, folder creation, modal drag-and-drop upload, multi-selection, clipboard copy & paste, embedding status badges, and direct open-in-tab editor integration.

## Public API Exposed
- `FileExplorer` (React.FC<{ onOpenFile?: (file: FileItem) => void }>): Main file manager component.

## Dependencies
- `src/api/endpoints/files.ts`:
  - `getFiles`
  - `uploadFiles`
  - `deleteFiles`
  - `deleteAllFiles`
  - `processFile`
  - `createDirectory`
  - `deleteDirectory`
  - `getFileContent`
  - `getFullFileContent`
  - `downloadFile`
- `src/api/ws.ts`: `progressWs` for real-time Huey worker progress updates
- `src/core/file-viewers/registry.ts`: `resolveViewer`
- `src/core/types/api.ts`: `FileItem`, `FileProgressItem`, `DirectoryResponse`
- `src/modules/file-viewers/UnsupportedViewerModal.tsx`: Unsupported format dialog

## How to Extend
- **File Actions**: Add new contextual toolbar actions by extending the selection action bar in `FileExplorer.tsx`.
- **Filtering & Search**: Add column sorting or search filtering over `currentDirectoryFiles`.
- **Folder nesting**: Uses standard Unix/Windows relative paths matching `endpoint.md`.

## Known Limitations / TODO
- Renaming existing folders uses `PATCH /files/directory?source=...&destination=...`.
- Selection is performed by clicking rows; the contextual action bar reserves its layout space so rows do not move when it appears.
- Drag-and-drop between rows can be added using HTML5 drag API.
