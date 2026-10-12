import { useState } from 'react';
import { ApiError } from '@/api/client';
import { users } from '@/api/endpoints/system';
import type { UserOut } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { AsyncState } from '@/ui/AsyncState';
import { useDialogs } from '@/ui/dialogContext';
import { Icon } from '@/ui/Icon';
import { Drawer } from '@/ui/Modal';
import { PageHeader } from '@/ui/PageHeader';
import { useToast } from '@/ui/toastContext';
import { LanguageList } from './LanguageList';
import { changesOf, draftOf, emptyDraft, payloadOf, type UserDraft } from './userForm';

function UserForm({ user, onClose, onSaved }: { user: UserOut | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [draft, setDraft] = useState<UserDraft>(user ? draftOf(user) : emptyDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const set = <K extends keyof UserDraft>(key: K, value: UserDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));

  const save = async () => {
    try {
      if (user) await users.update(user.id, changesOf(user, draft));
      else await users.create(payloadOf(draft));
      toast.show(user ? 'User saved' : 'User added');
      onSaved();
    } catch (reason) {
      if (reason instanceof ApiError && Object.keys(reason.fieldErrors).length > 0) setErrors(reason.fieldErrors);
      else toast.error(reason);
    }
  };

  const feedback = (key: string, hint: string) =>
    errors[key] ? <div className="form-error">{errors[key]}</div> : <div className="form-hint">{hint}</div>;

  const field = (key: 'name' | 'profession' | 'email' | 'age', label: string, hint: string, placeholder: string, type = 'text') => (
    <div className="form-group">
      <label className="form-label" htmlFor={`user-${key}`}>
        {label}
      </label>
      <input id={`user-${key}`} type={type} className="form-input" value={draft[key]} placeholder={placeholder} onChange={(event) => set(key, event.target.value)} />
      {feedback(key, hint)}
    </div>
  );

  return (
    <Drawer
      title={user ? `Edit ${user.name}` : 'Add a user'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" form="user-form" className="btn btn-primary" disabled={!draft.name.trim()}>
            Save
          </button>
        </>
      }
    >
      <form
        id="user-form"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        {field('name', 'Name', 'How agents should call this person.', 'e.g. Ada Lovelace')}
        {field('profession', 'Profession', 'Helps agents pick the right level of detail.', 'e.g. Data engineer')}
        <div className="form-group">
          <label className="form-label" htmlFor="user-description">
            About
          </label>
          <textarea
            id="user-description"
            className="form-textarea"
            rows={5}
            value={draft.description}
            onChange={(event) => set('description', event.target.value)}
            placeholder="Interests, goals, how they like answers to be written…"
          />
          {feedback('description', 'Anything agents should know about this person.')}
        </div>
        {field('age', 'Age', 'Optional.', 'e.g. 36', 'number')}
        <div className="form-group">
          <span className="form-label">Languages</span>
          <LanguageList value={draft.languages} onChange={(languages) => set('languages', languages)} />
          {feedback('languages', 'From the one you speak best to the least.')}
        </div>
        {field('email', 'Email', 'Optional.', 'name@example.com')}
      </form>
    </Drawer>
  );
}

export function UsersPage() {
  const toast = useToast();
  const dialogs = useDialogs();
  const list = useResource(users.list, []);
  const [editing, setEditing] = useState<{ user: UserOut | null } | null>(null);

  const remove = async (user: UserOut) => {
    if (!(await dialogs.confirm({ title: `Delete ${user.name}?`, confirmLabel: 'Delete', danger: true }))) return;
    try {
      await users.remove(user.id);
      toast.show('User deleted');
      await list.reload();
    } catch (reason) {
      toast.error(reason);
    }
  };

  return (
    <>
      <PageHeader
        title="Users"
        description="The people agents work for: who they are and what they do."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setEditing({ user: null })}>
            <Icon name="plus" /> Add a user
          </button>
        }
      />
      <AsyncState {...list} onRetry={list.reload} empty={<span className="muted">No user yet.</span>}>
        {(items) => (
          <div className="list">
            {items.map((user) => (
              <div key={user.id} className="list-row">
                <div className="list-row-main">
                  <div className="list-row-title">
                    <Icon name="user" size={16} /> {user.name}
                  </div>
                  <div className="list-row-meta">{[user.profession, user.age === null ? null : `${user.age} years old`, user.languages.join(', '), user.email].filter(Boolean).join(' · ') || 'No details yet'}</div>
                  {user.description && <div className="list-row-meta">{user.description}</div>}
                </div>
                <div className="list-row-actions">
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEditing({ user })}>
                    Edit
                  </button>
                  <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => remove(user)} aria-label={`Delete ${user.name}`}>
                    <Icon name="trash" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </AsyncState>
      {editing && (
        <UserForm
          user={editing.user}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void list.reload();
          }}
        />
      )}
    </>
  );
}
