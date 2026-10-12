import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { callable } from '@/test/callables';
import { CallableField } from './CallableField';
import { CallablePicker } from './CallablePicker';

const items = [
  callable('default', 'knowledge_base', 'search_knowledge_base', 'Search in the knowledge base.'),
  callable('default', 'smtp', 'send_email', 'Send an email.'),
  callable('default', 'smtp', 'read_inbox'),
  callable('custom', 'weather', 'forecast'),
];

const pick = (value: string[] = [], onConfirm = vi.fn()) => {
  render(<CallablePicker kind="tools" items={items} value={value} onConfirm={onConfirm} onClose={vi.fn()} />);
  return onConfirm;
};

describe('CallablePicker', () => {
  it('shows the modules of an extension as sections with their descriptions', () => {
    pick();

    const smtp = screen.getByRole('region', { name: 'smtp' });
    expect(within(smtp).getByText('default/smtp.py')).toBeTruthy();
    expect(within(smtp).getByText('Send an email.')).toBeTruthy();
    expect(screen.getByRole('region', { name: 'knowledge_base' })).toBeTruthy();
    expect(screen.queryByText('forecast')).toBeNull();
  });

  it('toggles one item, a whole module, then a whole extension, and confirms the selection', () => {
    const onConfirm = pick(['default-smtp-read_inbox']);

    fireEvent.click(screen.getByLabelText(/search_knowledge_base/));
    fireEvent.click(screen.getByLabelText('All tools of default/smtp.py'));
    expect((screen.getByLabelText(/send_email/) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /custom/ }));
    fireEvent.click(screen.getByLabelText('All tools of custom'));
    fireEvent.click(screen.getByText('Confirm'));

    expect(onConfirm).toHaveBeenCalledWith(['default-smtp-read_inbox', 'default-knowledge_base-search_knowledge_base', 'default-smtp-send_email', 'custom-weather-forecast']);
  });

  it('unchecks a whole extension once everything in it is chosen', () => {
    const onConfirm = pick(['custom-weather-forecast', 'default-smtp-send_email']);

    const all = screen.getByLabelText('All tools of default') as HTMLInputElement;
    expect(all.indeterminate).toBe(true);
    fireEvent.click(all);
    expect(all.checked).toBe(true);
    fireEvent.click(all);
    fireEvent.click(screen.getByText('Confirm'));

    expect(onConfirm).toHaveBeenCalledWith(['custom-weather-forecast']);
  });

  it('says how many items of each extension are chosen', () => {
    pick(['default-smtp-send_email']);

    expect(within(screen.getByRole('navigation', { name: 'Extensions' })).getByRole('button', { name: /default/ }).textContent).toContain('1/3');
  });
});

describe('CallableField', () => {
  it('changes nothing until the choice is confirmed', () => {
    const onChange = vi.fn();
    render(<CallableField kind="hooks" items={items} value={[]} onChange={onChange} emptyText="None installed." />);

    fireEvent.click(screen.getByText('Choose hooks…'));
    fireEvent.click(screen.getByLabelText(/send_email/));
    fireEvent.click(screen.getByText('Cancel'));
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('Choose hooks…'));
    fireEvent.click(screen.getByLabelText(/send_email/));
    fireEvent.click(screen.getByText('Confirm'));
    expect(onChange).toHaveBeenCalledWith(['default-smtp-send_email']);
    expect(screen.queryByText('Confirm')).toBeNull();
  });

  it('lists the chosen items, flags uninstalled ones and removes them', () => {
    const onChange = vi.fn();
    render(<CallableField kind="tools" items={items} value={['default-smtp-send_email', 'default-gone-tool']} onChange={onChange} emptyText="None installed." />);

    expect(screen.getByText('send_email')).toBeTruthy();
    expect(screen.getByText(/missing/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Remove default-gone-tool'));

    expect(onChange).toHaveBeenCalledWith(['default-smtp-send_email']);
  });

  it('is read only without onChange', () => {
    render(<CallableField kind="tools" items={items} value={['default-smtp-send_email']} emptyText="None installed." />);

    expect(screen.getByText('send_email')).toBeTruthy();
    expect(screen.queryByText('Choose tools…')).toBeNull();
    expect(screen.queryByLabelText('Remove send_email')).toBeNull();
  });
});
