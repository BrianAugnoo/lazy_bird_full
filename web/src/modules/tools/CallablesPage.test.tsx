import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { callable } from '@/test/callables';
import { mockApi } from '@/test/http';
import { ToastProvider } from '@/ui/Toasts';
import { CallablesPage } from './CallablesPage';

const hooks = [
  callable('default', 'system', 'date', 'Give the user\'s prompt the current date and time.'),
  callable('default', 'system', 'user_information', 'Give the system prompt who the user is.\n\nRead from the Users page.'),
  callable('default', 'compress', 'shorten'),
  callable('acme', 'guard', 'check', 'Refuse unsafe requests.'),
];

const renderPage = () =>
  render(
    <ToastProvider>
      <CallablesPage kind="hooks" />
    </ToastProvider>,
  );

describe('CallablesPage', () => {
  beforeEach(() => window.history.replaceState(null, '', '#/hooks'));
  afterEach(() => vi.restoreAllMocks());

  it('shows the modules of the default extension as sections, with each hook description', async () => {
    mockApi({ 'GET /hooks/': hooks, 'GET /hooks/settings': [] });
    renderPage();

    const system = await screen.findByRole('region', { name: 'system' });
    expect(within(system).getByText('default/system.py', { exact: false })).toBeTruthy();
    expect(within(system).getByText("Give the user's prompt the current date and time.")).toBeTruthy();
    expect(within(system).getByText(/Read from the Users page/)).toBeTruthy();
    expect(screen.getByRole('region', { name: 'compress' })).toBeTruthy();
    expect(screen.queryByText('Refuse unsafe requests.')).toBeNull();
  });

  it('switches extension from the side menu and keeps it in the address', async () => {
    mockApi({ 'GET /hooks/': hooks, 'GET /hooks/settings': [] });
    renderPage();

    const menu = await screen.findByRole('navigation', { name: 'Hooks extensions' });
    expect(within(menu).getAllByRole('button').map((button) => button.textContent)).toEqual(['default3', 'custom0', 'acme1']);
    fireEvent.click(within(menu).getByRole('button', { name: /acme/ }));

    expect(await screen.findByText('Refuse unsafe requests.')).toBeTruthy();
    expect(window.location.hash).toBe('#/hooks?extension=acme');
    fireEvent.click(within(menu).getByRole('button', { name: /custom/ }));
    expect(await screen.findByText('No hooks in custom')).toBeTruthy();
  });
});
