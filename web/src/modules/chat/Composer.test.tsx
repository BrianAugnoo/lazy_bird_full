import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Composer } from './Composer';
import { RouteContext } from '@/core/router';

describe('chat composer', () => {
  it('sends with Enter and exposes unavailable controls without invoking commands', () => {
    const send = vi.fn(); const stop = vi.fn();
    render(<Composer placeholder="Message…" running={false} onSend={send} onStop={stop} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A useful question' } });
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter', shiftKey: true });
    expect(send).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(send).toHaveBeenCalledWith('A useful question');
    fireEvent.click(screen.getByRole('button', { name: 'Add to message' }));
    expect(screen.getAllByText('Coming soon')).toHaveLength(3);
    fireEvent.click(screen.getByRole('button', { name: /Create an image/ }));
    fireEvent.click(screen.getByRole('button', { name: /Audio/ }));
    expect(send).toHaveBeenCalledTimes(1); expect(stop).not.toHaveBeenCalled();
  });
  it('does not stop a background conversation when Escape is pressed in another tab', () => {
    const stop = vi.fn();
    render(<RouteContext.Provider value={{ route: { page: 'chat', params: {} }, active: false, setParams: vi.fn() }}><Composer placeholder="Message…" running onSend={vi.fn()} onStop={stop} /></RouteContext.Provider>);
    fireEvent.keyDown(window, { key: 'Escape' }); expect(stop).not.toHaveBeenCalled();
  });
});
