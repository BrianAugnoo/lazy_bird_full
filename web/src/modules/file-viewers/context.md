# Context Module — file-viewers

## Goal
Provides the extensible file viewing and editing system for lazy_bird, following the Open/Closed contract defined in `src/core/file-viewers/registry.ts`. Files can be edited in dedicated tabs with live preview, toolbar formatting, and direct persistence via `PUT /files/{id}/content`.

## Public API Exposed
- `registerAllBuiltinViewers()`: Registers standard viewers (MarkdownViewer, TextCodeViewer).
- `MarkdownViewer`: Rich Markdown editor using `marked` + `DOMPurify` with Edit, Split, and Preview modes.
- `TextCodeViewer`: Code and plain text viewer/editor with line numbering.
- `UnsupportedViewerModal`: Dialog shown when an unsupported file format is opened, offering direct download.
- `FileViewerModal`: Optional standalone modal wrapper for viewers.
- Types: `FileViewerProps`, `FileViewerModule` exported from `@/core/file-viewers/types`.

## Dependencies
- `marked` & `dompurify`: Safe, high-performance client-side Markdown parsing and sanitization.
- `src/core/file-viewers/registry.ts`: Priority-based viewer resolution.
- `src/api/endpoints/files.ts`: `getFileContent`, `updateFileContent`, `downloadFile`, `processFile`.
- `src/core/types/api.ts`: `FileItem`.

## How to Extend
To support a new file format (e.g. PDF or Image):
1. Create a subfolder in `src/modules/file-viewers/<format>/`.
2. Implement a React component conforming to `FileViewerProps`.
3. Register the viewer:
   ```ts
   registerViewer({
     id: 'pdf-viewer',
     name: 'PDF Reader',
     icon: '📄',
     priority: 10,
     canHandle: (ext) => ext.toLowerCase() === 'pdf',
     Component: PDFViewer,
   });
   ```

## Known Limitations / TODO
- Monaco editor or syntax highlighter can be added to `TextCodeViewer` for full syntax coloration of complex programming languages.
- The application loads editor text through `GET /files/{file_id}/content`; binary files are not supported by the text editors.
