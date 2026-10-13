export interface ExtensionItem { extension: string }
export function libraryExtensions(items: ExtensionItem[]) {
  const names = ['default', 'custom', ...[...new Set(items.map(item => item.extension))].filter(name => name !== 'default' && name !== 'custom').sort()];
  return names.map(extension => ({ extension, count: items.filter(item => item.extension === extension).length }));
}
export function librarySelection(items: ExtensionItem[], requested?: string): string {
  const extensions = libraryExtensions(items);
  return extensions.some(entry => entry.extension === requested) ? requested! : extensions.find(entry => entry.count > 0)?.extension ?? 'default';
}
