import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { UserOut } from '@/core/types/api';
import { mockApi } from '@/test/http';
import { DialogProvider } from '@/ui/Dialogs';
import { ToastProvider } from '@/ui/Toasts';
import { UsersPage } from './UsersPage';

const ada: UserOut = {
  id: 1,
  name: 'Ada',
  description: 'Writes compilers',
  profession: 'Engineer',
  email: null,
  age: 36,
  languages: ['French', 'English'],
  meta: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const active = (user: UserOut) => ({ user_id: user.id, user });

const renderPage = () =>
  render(
    <ToastProvider>
      <DialogProvider>
        <UsersPage />
      </DialogProvider>
    </ToastProvider>,
  );

describe('UsersPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists the users with their profession and language', async () => {
    mockApi({ 'GET /users/': [ada], 'GET /profile/': active(ada) });
    renderPage();

    expect(await screen.findByText('Ada')).toBeTruthy();
    expect(screen.getByText('Engineer · 36 years old · French, English')).toBeTruthy();
    expect(screen.getByText('Writes compilers')).toBeTruthy();
  });

  it('says when there is no user yet', async () => {
    mockApi({ 'GET /users/': [], 'GET /profile/': { user_id: null, user: null } });
    renderPage();

    expect(await screen.findByText('No user yet.')).toBeTruthy();
  });

  it('adds a user, leaving empty fields out', async () => {
    const sent = mockApi({ 'GET /users/': [], 'GET /profile/': { user_id: null, user: null }, 'POST /users/': { ...ada, id: 2, name: 'Bob' } });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /add a user/i }));

    const save = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Bob' } });
    fireEvent.change(screen.getByLabelText('Profession'), { target: { value: 'Teacher' } });
    fireEvent.click(save);

    await waitFor(() => expect(sent('POST /users/')).toHaveLength(1));
    expect(sent('POST /users/')[0]).toEqual({ name: 'Bob', description: null, profession: 'Teacher', email: null, age: null, languages: [] });
  });

  it('collects ranked languages and age when adding a user', async () => {
    const sent = mockApi({ 'GET /users/': [], 'GET /profile/': { user_id: null, user: null }, 'POST /users/': { ...ada, id: 2 } });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /add a user/i }));

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Bob' } });
    fireEvent.change(screen.getByLabelText('Age'), { target: { value: '41' } });
    for (const language of ['English', 'French', 'Spanish']) {
      fireEvent.change(screen.getByLabelText('Add a language'), { target: { value: language } });
      fireEvent.keyDown(screen.getByLabelText('Add a language'), { key: 'Enter' });
    }
    fireEvent.click(screen.getByRole('button', { name: 'Move Spanish up' }));
    fireEvent.click(screen.getByRole('button', { name: 'Move Spanish up' }));
    fireEvent.click(screen.getByRole('button', { name: 'Remove English' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(sent('POST /users/')).toHaveLength(1));
    expect(sent('POST /users/')[0]).toMatchObject({ age: 41, languages: ['Spanish', 'French'] });
  });

  it('edits a user by sending only what changed', async () => {
    const sent = mockApi({ 'GET /users/': [ada], 'GET /profile/': active(ada), 'PATCH /users/1': { ...ada, profession: 'Mathematician' } });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));

    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Ada');
    fireEvent.change(screen.getByLabelText('Profession'), { target: { value: 'Mathematician' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(sent('PATCH /users/1')).toHaveLength(1));
    expect(sent('PATCH /users/1')[0]).toEqual({ profession: 'Mathematician' });
  });

  it('shows the error of a field next to it', async () => {
    mockApi({
      'GET /users/': [ada],
      'PATCH /users/1': { status: 422, body: { error: { code: 'invalid_request', message: 'Invalid', details: { fields: { email: 'Not an email address.' } } } } },
    });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'oops' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Not an email address.')).toBeTruthy();
  });

  it('deletes a user after confirmation', async () => {
    const sent = mockApi({ 'GET /users/': [ada], 'GET /profile/': active(ada), 'DELETE /users/1': undefined });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Delete Ada' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(sent('DELETE /users/1')).toHaveLength(1));
  });

  it('marks the active user and offers to switch to the others', async () => {
    const bob = { ...ada, id: 2, name: 'Bob' };
    mockApi({ 'GET /users/': [ada, bob], 'GET /profile/': active(ada) });
    renderPage();

    expect(await screen.findByText('Bob')).toBeTruthy();
    expect(screen.getAllByText('Active')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: 'Make Ada active' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Make Bob active' })).toBeTruthy();
  });

  it('switches the active user', async () => {
    const bob = { ...ada, id: 2, name: 'Bob' };
    let current = ada;
    const sent = mockApi({
      'GET /users/': [ada, bob],
      'GET /profile/': () => active(current),
      'PUT /profile/': (body: unknown) => {
        current = (body as { user_id: number }).user_id === 2 ? bob : ada;
        return active(current);
      },
    });
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Make Bob active' }));

    await waitFor(() => expect(sent('PUT /profile/')).toEqual([{ user_id: 2 }]));
    expect(await screen.findByRole('button', { name: 'Make Ada active' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Make Bob active' })).toBeNull();
  });

  it('offers no switch when there is a single user', async () => {
    mockApi({ 'GET /users/': [ada], 'GET /profile/': active(ada) });
    renderPage();

    expect(await screen.findByText('Active')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /make .* active/i })).toBeNull();
  });
});
