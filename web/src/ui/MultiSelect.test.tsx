import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MultiSelect } from './MultiSelect';

describe('MultiSelect', () => {
  it('toggles options and keeps the selection order', () => {
    const onChange = vi.fn();
    const options = [
      { value: 'a', label: 'Alpha' },
      { value: 'b', label: 'Beta' },
    ];
    render(<MultiSelect options={options} value={['b']} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Alpha'));
    expect(onChange).toHaveBeenLastCalledWith(['b', 'a']);
    fireEvent.click(screen.getByLabelText('Beta'));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it('shows selected values that are no longer installed so they can be removed', () => {
    const onChange = vi.fn();
    render(<MultiSelect options={[]} value={['default-gone-tool']} onChange={onChange} />);
    expect(screen.getByText('missing')).toBeTruthy();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
