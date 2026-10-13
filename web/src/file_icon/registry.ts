import registry from './registry.json';
const assets = import.meta.glob<string>('./*.svg', { eager: true, query: '?url', import: 'default' });

/** Registry entries are assets, not backend URLs. Unknown extensions always resolve. */
export function fileIconAsset(extension: string): string {
  const key = extension.toLowerCase().replace(/^\./, '');
  const name = (registry as Record<string, string>)[key] ?? registry.default;
  return assets[`./${name}`] ?? assets[`./${registry.default}`];
}
