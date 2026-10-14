/**
 * Page registry: every screen registers itself here and the shell builds the
 * sidebar from it. Adding a screen never requires editing the shell.
 */
import type { ComponentType } from 'react';
import type { IconName } from '@/ui/Icon';

export type NavGroup = 'Work' | 'Agents' | 'Models' | 'System';
export const NAV_GROUPS: NavGroup[] = ['Work', 'Agents', 'Models', 'System'];

export interface PageDefinition {
  id: string;
  group: NavGroup;
  label: string;
  icon: IconName;
  /** Sort order inside the group. */
  order: number;
  component: ComponentType;
  /** Full-bleed pages (chat) manage their own scrolling and padding. */
  flush?: boolean;
  /** Hide duplicate navigation entries while retaining the route and page search. */
  sidebar?: boolean;
}

const pages = new Map<string, PageDefinition>();

export function registerPage(page: PageDefinition): void {
  pages.set(page.id, page);
}

export function getPage(id: string): PageDefinition | undefined {
  return pages.get(id);
}

export function pagesByGroup(): Array<{ group: NavGroup; pages: PageDefinition[] }> {
  return NAV_GROUPS.map((group) => ({
    group,
    pages: [...pages.values()].filter((page) => page.group === group).sort((a, b) => a.order - b.order),
  })).filter((entry) => entry.pages.length > 0);
}

export function firstPage(): PageDefinition | undefined {
  return pagesByGroup()[0]?.pages[0];
}
