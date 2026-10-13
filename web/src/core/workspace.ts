import { buildHash, parseHash, type Route, type RouteChanges } from './router';

export interface WorkspaceTab { id: string; route: Route; views: Record<string, Route> }
export interface WorkspaceSplit { left: string; right: string; ratio: number }
export interface Workspace { tabs: WorkspaceTab[]; active: string; split?: WorkspaceSplit }
export const WORKSPACE_KEY = 'lazy-bird.workspace.v1';
export const splitRatio = (value: number) => Math.max(25, Math.min(75, Number.isFinite(value) ? value : 50));

export function newTab(route: Route): WorkspaceTab {
  const copied = { page: route.page, params: { ...route.params } };
  return { id: crypto.randomUUID(), route: copied, views: { [route.page]: copied } };
}

export function selectTab(workspace: Workspace, id: string): Workspace {
  if (!workspace.tabs.some(tab => tab.id === id)) return workspace;
  const split = workspace.split;
  if (!split || split.left === id || split.right === id) return { ...workspace, active: id };
  const side = workspace.active === split.right ? 'right' : 'left';
  return { ...workspace, active: id, split: { ...split, [side]: id } };
}

/** Menu navigation changes only the focused tab, remembering its visited pages. */
export function navigateWorkspace(workspace: Workspace, page: string, params?: Record<string, string>, extra = false): Workspace {
  const current = workspace.tabs.find(tab => tab.id === workspace.active)!;
  const route = params ? { page, params } : current.views[page] ?? { page, params: {} };
  if (extra) { const tab = newTab(route); return selectTab({ ...workspace, tabs: [...workspace.tabs, tab] }, tab.id); }
  return { ...workspace, tabs: workspace.tabs.map(tab => tab.id === current.id ? { ...tab, route, views: { ...tab.views, [page]: route } } : tab) };
}

export function updateTabParams(workspace: Workspace, id: string, page: string, changes: RouteChanges): Workspace {
  return { ...workspace, tabs: workspace.tabs.map(tab => {
    if (tab.id !== id) return tab;
    const previous = tab.views[page] ?? { page, params: {} };
    const route = parseHash(buildHash(page, { ...previous.params, ...changes }));
    return { ...tab, route: tab.route.page === page ? route : tab.route, views: { ...tab.views, [page]: route } };
  }) };
}

export function duplicateTab(workspace: Workspace): Workspace {
  const source = workspace.tabs.find(tab => tab.id === workspace.active)!;
  const tab = newTab(source.route);
  return selectTab({ ...workspace, tabs: [...workspace.tabs, tab] }, tab.id);
}

export function toggleSplit(workspace: Workspace): Workspace {
  if (workspace.split) return { ...workspace, split: undefined };
  const existing = [...workspace.tabs].reverse().find(tab => tab.id !== workspace.active);
  const tab = existing ?? newTab(workspace.tabs.find(item => item.id === workspace.active)!.route);
  return { ...workspace, tabs: existing ? workspace.tabs : [...workspace.tabs, tab], active: tab.id, split: { left: workspace.active, right: tab.id, ratio: 50 } };
}

export function removeTab(workspace: Workspace, id: string, fallback: string): Workspace {
  const index = workspace.tabs.findIndex(tab => tab.id === id);
  if (index < 0) return workspace;
  let tabs = workspace.tabs.filter(tab => tab.id !== id);
  if (!tabs.length) tabs = [newTab({ page: fallback, params: {} })];
  const split = workspace.split;
  if (split && (split.left === id || split.right === id)) return { tabs, active: split.left === id ? split.right : split.left };
  return { ...workspace, tabs, active: workspace.active === id ? tabs[Math.min(index, tabs.length - 1)].id : workspace.active };
}

/** Restore addresses and layout only; migrate old tab records and reject obsolete pages. */
export function restoreWorkspace(hash: string, validPage: (id: string) => boolean, fallback: string): Workspace {
  let tabs: WorkspaceTab[] = []; let active = ''; let split: WorkspaceSplit | undefined;
  const validRoute = (route: Route) => route && validPage(route.page) && route.params && typeof route.params === 'object' && !Array.isArray(route.params) && Object.values(route.params).every(value => typeof value === 'string');
  try {
    const saved = JSON.parse(sessionStorage.getItem(WORKSPACE_KEY) ?? 'null');
    if (Array.isArray(saved?.tabs)) {
      const ids = new Set<string>();
      for (const tab of saved.tabs) {
        if (!tab || typeof tab.id !== 'string' || ids.has(tab.id) || !validRoute(tab.route)) continue;
        ids.add(tab.id);
        const views = Object.fromEntries(Object.entries(tab.views ?? {}).filter(([key, route]) => validRoute(route as Route) && (route as Route).page === key));
        tabs.push({ id: tab.id, route: tab.route, views: { ...views, [tab.route.page]: tab.route } });
      }
      active = tabs.some(tab => tab.id === saved.active) ? saved.active : tabs[0]?.id;
      if (saved.split && saved.split.left !== saved.split.right && ids.has(saved.split.left) && ids.has(saved.split.right)) split = { left: saved.split.left, right: saved.split.right, ratio: splitRatio(saved.split.ratio) };
    }
  } catch { /* Storage is optional. */ }
  if (!tabs.length) { const tab = newTab({ page: fallback, params: {} }); tabs = [tab]; active = tab.id; }
  if (split && active !== split.left && active !== split.right) active = split.left;
  let workspace: Workspace = { tabs, active, ...(split ? { split } : {}) };
  const address = parseHash(hash);
  if (validRoute(address)) {
    const matching = tabs.find(tab => buildHash(tab.route.page, tab.route.params) === buildHash(address.page, address.params));
    workspace = matching ? selectTab(workspace, matching.id) : navigateWorkspace(workspace, address.page, address.params);
  }
  return workspace;
}
