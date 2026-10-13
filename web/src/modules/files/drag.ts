export const FILE_DRAG_TYPE = 'application/x-lazy-bird-files';
export type FileDrag = { kind: 'files'; ids: number[] } | { kind: 'folder'; path: string };

export function parseFileDrag(raw: string): FileDrag | null {
  try {
    const value = JSON.parse(raw);
    if (value.kind === 'files' && Array.isArray(value.ids) && value.ids.length && value.ids.every((id: unknown) => typeof id === 'number' && Number.isSafeInteger(id) && id > 0)) return { kind: 'files', ids: [...new Set<number>(value.ids)] };
    if (value.kind === 'folder' && typeof value.path === 'string' && value.path && !value.path.split('/').some((part: string) => !part || part === '..' || part === '.')) return { kind: 'folder', path: value.path };
  } catch { /* External drags and invalid payloads are ignored. */ }
  return null;
}
export function validDestination(drag: FileDrag, destination: string): boolean {
  return drag.kind === 'files' || (destination !== drag.path && !destination.startsWith(`${drag.path}/`) && destination !== drag.path.split('/').slice(0, -1).join('/'));
}
