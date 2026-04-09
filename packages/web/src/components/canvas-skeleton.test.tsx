import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CanvasSkeleton } from '@unrealmake/shared/components/production/canvas/CanvasSkeleton';

describe('CanvasSkeleton', () => {
  it('renders the container with data-testid', async () => {
    render(<CanvasSkeleton />);
    expect(await screen.findByTestId('canvas-skeleton')).toBeTruthy();
  });

  it('renders a dot-grid background element', async () => {
    render(<CanvasSkeleton />);
    expect(await screen.findByTestId('canvas-skeleton-dotgrid')).toBeTruthy();
  });

  it('renders at least 3 placeholder node cards', async () => {
    render(<CanvasSkeleton />);
    const cards = await screen.findAllByTestId(/^skeleton-node-/);
    expect(cards.length).toBeGreaterThanOrEqual(3);
  });

  it('renders a loading hint text', async () => {
    render(<CanvasSkeleton />);
    const hint = await screen.findByTestId('canvas-skeleton-hint');
    expect(hint.textContent).toBeTruthy();
    expect(hint.textContent!.length).toBeGreaterThan(0);
  });

  it('accepts and applies a custom className', async () => {
    render(<CanvasSkeleton className="my-custom" />);
    const root = await screen.findByTestId('canvas-skeleton');
    expect(root.className).toContain('my-custom');
  });

  it('placeholder nodes do NOT have pulse animation by default', async () => {
    render(<CanvasSkeleton />);
    const cards = await screen.findAllByTestId(/^skeleton-node-/);
    cards.forEach((card) => {
      expect(card.className).not.toContain('animate-pulse');
    });
  });
});
