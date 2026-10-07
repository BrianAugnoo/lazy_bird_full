/** Folder paths inside the storage use `/` and no leading slash; `''` is the root. */

export const joinPath = (dir: string, name: string) => (dir ? `${dir}/${name}` : name);

export const parentOf = (path: string) => (path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '');

export const baseName = (path: string) => path.slice(path.lastIndexOf('/') + 1);

/** Direct sub-folders of `dir` among every known folder. */
export function childFolders(dir: string, directories: string[]): string[] {
  const prefix = dir ? `${dir}/` : '';
  const children = new Set<string>();
  for (const path of directories) {
    if (!path.startsWith(prefix) || path === dir) continue;
    const rest = path.slice(prefix.length);
    if (rest) children.add(joinPath(dir, rest.split('/')[0]));
  }
  return [...children].sort((a, b) => a.localeCompare(b));
}

/** `a/b/c` → [{name: 'a', path: 'a'}, {name: 'b', path: 'a/b'}, …]. */
export function breadcrumbs(dir: string): Array<{ name: string; path: string }> {
  if (!dir) return [];
  const parts = dir.split('/');
  return parts.map((name, index) => ({ name, path: parts.slice(0, index + 1).join('/') }));
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}
