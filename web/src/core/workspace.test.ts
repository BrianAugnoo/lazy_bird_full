import { afterEach, describe, expect, it } from 'vitest';
import { duplicateTab, navigateWorkspace, newTab, removeTab, restoreWorkspace, selectTab, toggleSplit, updateTabParams, WORKSPACE_KEY } from './workspace';

describe('workspace addresses', () => {
  afterEach(() => sessionStorage.clear());
  const valid = (id: string) => ['chat', 'files', 'tools'].includes(id);
  it('creates an initial page and respects a deep link', () => {
    expect(restoreWorkspace('', valid, 'chat').tabs[0].route).toEqual({ page: 'chat', params: {} });
    expect(restoreWorkspace('#/files?file=12', valid, 'chat').tabs[0].route).toEqual({ page: 'files', params: { file: '12' } });
  });
  it('restores tab addresses and navigates unmatched deep links in the active tab', () => {
    const chat = newTab({ page: 'chat', params: { session: '1' } });
    const files = newTab({ page: 'files', params: { dir: 'docs' } });
    sessionStorage.setItem(WORKSPACE_KEY, JSON.stringify({ tabs: [chat, files], active: files.id }));
    expect(restoreWorkspace('', valid, 'chat').active).toBe(files.id);
    expect(restoreWorkspace('#/chat?session=1', valid, 'chat').active).toBe(chat.id);
    const linked = restoreWorkspace('#/tools', valid, 'chat');
    expect(linked.tabs).toHaveLength(2);
    expect(linked.tabs.find(tab => tab.id === linked.active)?.route.page).toBe('tools');
  });
  it('rejects corrupt, duplicate and no-longer-registered tabs', () => {
    sessionStorage.setItem(WORKSPACE_KEY, '{bad json');
    expect(restoreWorkspace('', valid, 'chat').tabs).toHaveLength(1);
    const tab = newTab({ page: 'files', params: {} });
    sessionStorage.setItem(WORKSPACE_KEY, JSON.stringify({ tabs: [null, tab, tab, { id: 'bad', route: { page: 'missing', params: {} } }, { id: 'array', route: { page: 'files', params: [] } }], active: 'bad' }));
    const result = restoreWorkspace('', valid, 'chat');
    expect(result.tabs).toEqual([tab]); expect(result.active).toBe(tab.id);
  });
  it('menu navigation keeps the same tab and remembers previous page locations', () => {
    const tab = newTab({ page: 'chat', params: { session: '1', conversation: '3' } });
    const original = { tabs: [tab], active: tab.id };
    const files = navigateWorkspace(original, 'files');
    expect(files.tabs).toHaveLength(1); expect(files.active).toBe(tab.id);
    expect(files.tabs[0].route.page).toBe('files');
    expect(navigateWorkspace(files, 'chat').tabs[0].route).toEqual(tab.route);
    const loaded = updateTabParams(files, tab.id, 'chat', { conversation: 4 });
    expect(loaded.tabs[0].route.page).toBe('files');
    expect(loaded.tabs[0].views.chat.params.conversation).toBe('4');
  });
  it('new tabs copy the complete focused address without adding another page', () => {
    const tab = newTab({ page: 'files', params: { dir: 'docs', file: '12' } });
    const workspace = duplicateTab({ tabs: [tab], active: tab.id });
    expect(workspace.tabs).toHaveLength(2);
    expect(workspace.tabs[1].route).toEqual(tab.route);
    expect(workspace.active).toBe(workspace.tabs[1].id);
    expect(workspace.tabs[1].id).not.toBe(tab.id);
  });
  it('split panes navigate independently and closing split keeps both tabs', () => {
    const tab = newTab({ page: 'chat', params: { session: '1' } });
    const split = toggleSplit({ tabs: [tab], active: tab.id });
    expect(split.split).toEqual({ left: tab.id, right: split.active, ratio: 50 });
    const right = navigateWorkspace(split, 'files');
    expect(right.tabs.find(item => item.id === tab.id)?.route.page).toBe('chat');
    const left = navigateWorkspace(selectTab(right, tab.id), 'tools');
    expect(left.tabs.find(item => item.id === split.active)?.route.page).toBe('files');
    const joined = toggleSplit(left);
    expect(joined.split).toBeUndefined(); expect(joined.tabs).toHaveLength(2);
    expect(toggleSplit(joined).tabs).toHaveLength(2);
    const closed = removeTab(left, tab.id, 'chat');
    expect(closed.split).toBeUndefined(); expect(closed.active).toBe(split.active);
  });
  it('restores valid split geometry and rejects duplicate/obsolete pane IDs', () => {
    const left = newTab({ page: 'chat', params: {} }); const right = newTab({ page: 'files', params: {} });
    sessionStorage.setItem(WORKSPACE_KEY, JSON.stringify({ tabs: [left, right], active: right.id, split: { left: left.id, right: right.id, ratio: 100 } }));
    expect(restoreWorkspace('', valid, 'chat').split?.ratio).toBe(75);
    sessionStorage.setItem(WORKSPACE_KEY, JSON.stringify({ tabs: [left, right], active: right.id, split: { left: left.id, right: left.id, ratio: 50 } }));
    expect(restoreWorkspace('', valid, 'chat').split).toBeUndefined();
  });
});
