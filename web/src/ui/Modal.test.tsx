import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Drawer, Modal } from './Modal';

describe('overlays', () => {
  it('close one at a time with Escape, the last opened first', () => {
    const closeDrawer = vi.fn();
    const closeModal = vi.fn();
    const drawer = (withModal: boolean) => (
      <Drawer title="Agent" onClose={closeDrawer}>
        {withModal && (
          <Modal title="Choose tools" onClose={closeModal}>
            list
          </Modal>
        )}
      </Drawer>
    );
    const { rerender } = render(drawer(false));
    rerender(drawer(true));

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(closeModal).toHaveBeenCalledTimes(1);
    expect(closeDrawer).not.toHaveBeenCalled();

    rerender(drawer(false));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(closeDrawer).toHaveBeenCalledTimes(1);
    expect(closeModal).toHaveBeenCalledTimes(1);
  });
});
