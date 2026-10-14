import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ResourceSnapshot } from '@/core/types/api';
import { Resources } from './Resources';

describe('Resources', () => {
  it('shows whole-PC usage against physical capacity and keeps pool reservations separate', () => {
    const resources: ResourceSnapshot = {
      capacity: { cpu: 8, ram_mb: 8192, vram_mb: 4096 },
      used: { cpu: 1, ram_mb: 1024, vram_mb: 512 },
      holders: {},
      system: {
        ram_mb: { total_mb: 16384, used_mb: 10240, available_mb: 6144 },
        vram_mb: { total_mb: 8192, used_mb: 3072, available_mb: 4864 },
      },
    };
    const { rerender } = render(<Resources resources={resources} />);
    const ram = within(screen.getByRole('group', { name: 'Memory' }));
    expect(ram.getByText('10.0 GB / 16.0 GB')).toBeTruthy();
    expect(ram.getByText('Whole PC · 6.0 GB available')).toBeTruthy();
    expect(ram.getByText('1.0 GB reserved by lazy_bird (limit 8.0 GB)')).toBeTruthy();
    expect(ram.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('63');
    const gpu = within(screen.getByRole('group', { name: 'GPU memory' }));
    expect(gpu.getByText('3.0 GB / 8.0 GB')).toBeTruthy();
    expect(gpu.getByText('Whole PC · 4.8 GB available')).toBeTruthy();
    expect(screen.getByText('1 / 8')).toBeTruthy();

    rerender(<Resources resources={{ ...resources, system: { ...resources.system, ram_mb: { total_mb: 16384, used_mb: 12288, available_mb: 4096 } } }} />);
    expect(ram.getByText('12.0 GB / 16.0 GB')).toBeTruthy();
    expect(ram.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('75');
  });

  it('does not present unavailable telemetry or an older server\'s reservations as real usage', () => {
    const resources: ResourceSnapshot = { capacity: { ram_mb: 16384 }, used: { ram_mb: 1024 }, holders: {} };
    const { rerender } = render(<Resources resources={resources} />);
    expect(screen.getByText('Usage unavailable')).toBeTruthy();
    expect(screen.queryByRole('progressbar')).toBeNull();
    expect(screen.getByText('1.0 GB reserved by lazy_bird (limit 16.0 GB)')).toBeTruthy();
    rerender(<Resources resources={{ ...resources, system: { ram_mb: null } }} />);
    expect(screen.getByText('Usage unavailable')).toBeTruthy();
  });
});
