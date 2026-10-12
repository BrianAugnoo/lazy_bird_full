import { describe, expect, it } from 'vitest';
import type { UserOut } from '@/core/types/api';
import { addLanguage, changesOf, draftOf, emptyDraft, moveLanguage, payloadOf } from './userForm';

const user: UserOut = {
  id: 1,
  name: 'Ada',
  description: null,
  profession: 'Engineer',
  email: null,
  age: 36,
  languages: ['French', 'English'],
  meta: { timezone: 'Europe/Paris' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('user form', () => {
  it('sends empty optional fields as nothing and trims text', () => {
    expect(payloadOf({ ...emptyDraft, name: '  Ada ', profession: '   ', languages: ['French'] })).toEqual({
      name: 'Ada',
      description: null,
      profession: null,
      email: null,
      age: null,
      languages: ['French'],
    });
  });

  it('turns the age text into a number', () => {
    expect(payloadOf({ ...emptyDraft, name: 'Ada', age: '36' }).age).toBe(36);
  });

  it('shows missing values as empty fields', () => {
    expect(draftOf(user)).toMatchObject({ name: 'Ada', description: '', email: '', age: '36', languages: ['French', 'English'] });
  });

  it('sends nothing for a user left as it was, and never its meta', () => {
    expect(changesOf(user, draftOf(user))).toEqual({});
    expect(payloadOf(draftOf(user))).not.toHaveProperty('meta');
  });

  it('sends only the fields that changed, clearing the ones emptied', () => {
    const draft = { ...draftOf(user), profession: '', description: 'Writes compilers', age: '', languages: ['English', 'French'] };

    expect(changesOf(user, draft)).toEqual({ profession: null, description: 'Writes compilers', age: null, languages: ['English', 'French'] });
  });

  it('adds languages at the end, once each', () => {
    expect(addLanguage(['French'], ' English ')).toEqual(['French', 'English']);
    expect(addLanguage(['French'], 'french')).toEqual(['French']);
    expect(addLanguage(['French'], '  ')).toEqual(['French']);
  });

  it('moves a language toward the best or the worst, never past the ends', () => {
    expect(moveLanguage(['A', 'B', 'C'], 2, -1)).toEqual(['A', 'C', 'B']);
    expect(moveLanguage(['A', 'B', 'C'], 0, 1)).toEqual(['B', 'A', 'C']);
    expect(moveLanguage(['A', 'B', 'C'], 0, -1)).toEqual(['A', 'B', 'C']);
    expect(moveLanguage(['A', 'B', 'C'], 2, 1)).toEqual(['A', 'B', 'C']);
  });
});
