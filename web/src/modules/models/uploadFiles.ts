/** A file picked for upload, with its path inside the model folder. */
export interface PickedFile {
  file: File;
  path: string;
}

/**
 * Paths of picked files inside the model: a picked folder keeps its structure
 * without the folder itself (`my-model/config.json` → `config.json`); hidden files
 * (`.git/…`, `.DS_Store`) are left out.
 */
export function pickedFiles(files: File[]): PickedFile[] {
  const entries = files
    .map((file) => ({ file, parts: (file.webkitRelativePath || file.name).split('/').filter(Boolean) }))
    .filter(({ parts }) => parts.length > 0 && !parts.some((part) => part.startsWith('.')));
  const top = entries[0]?.parts[0];
  const shared = entries.length > 0 && entries.every(({ parts }) => parts.length > 1 && parts[0] === top);
  return entries.map(({ file, parts }) => ({ file, path: (shared ? parts.slice(1) : parts).join('/') }));
}

/** A model name suggested from what was picked: the folder name, or the file name without extension. */
export function suggestedName(files: File[]): string {
  const first = files[0];
  if (!first) return '';
  const folder = first.webkitRelativePath.split('/')[0];
  if (first.webkitRelativePath && folder) return folder;
  return first.name.replace(/\.[^.]+$/, '');
}
