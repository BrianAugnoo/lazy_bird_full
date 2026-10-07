import { describe, expect, it } from 'vitest';
import { socketUrl } from './socket';

describe('socketUrl', () => {
  it('follows the page address when the API is proxied', () => {
    expect(socketUrl('/ws/tasks')).toBe(`ws://${window.location.host}/api/ws/tasks`);
  });
});
