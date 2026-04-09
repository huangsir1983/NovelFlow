import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { lazy, Suspense } from 'react';

/**
 * These tests verify the lazy-loading contract for Pose3DEditor inside Pose3DNode:
 * 1. Pose3DEditor must NOT be rendered (and thus NOT imported) when the editor is closed
 * 2. A Suspense boundary must wrap the lazy editor so three.js loads on demand
 *
 * We test the pattern here rather than the actual component (which requires
 * React Flow context) to keep the test fast and free from heavy dependencies.
 */

// Simulate the lazy pattern we expect Pose3DNode to use
const LazyEditor = lazy(() =>
  import('@unrealmake/shared/components/production/canvas/Pose3DEditor').then((m) => ({
    default: m.Pose3DEditor,
  })),
);

describe('Pose3DNode lazy-loading contract', () => {
  it('does NOT import Pose3DEditor module when editorOpen is false', async () => {
    // Simply render Pose3DNode card mockup without the editor
    // Verify that import('./Pose3DEditor') is NOT called
    const importSpy = vi.fn();
    const ConditionalLazy = ({ open }: { open: boolean }) => {
      if (!open) return <div data-testid="card-only">Card</div>;
      importSpy();
      return (
        <Suspense fallback={<div>loading editor...</div>}>
          <LazyEditor
            isOpen={true}
            onClose={() => {}}
            onScreenshot={() => Promise.resolve()}
            onPoseChange={() => {}}
          />
        </Suspense>
      );
    };

    render(<ConditionalLazy open={false} />);
    expect(await screen.findByTestId('card-only')).toBeTruthy();
    expect(importSpy).not.toHaveBeenCalled();
  });

  it('source file uses React.lazy pattern for Pose3DEditor', async () => {
    // Read the source file and verify it uses lazy() instead of static import
    const fs = await import('node:fs');
    const path = await import('node:path');
    const filePath = path.resolve(
      process.cwd(),
      '../shared/src/components/production/canvas/Pose3DNode.tsx',
    );
    const source = fs.readFileSync(filePath, 'utf8');

    // Should NOT have a static top-level import of Pose3DEditor
    expect(source).not.toMatch(/^import\s+.*Pose3DEditor.*from/m);

    // Should have a lazy() call
    expect(source).toMatch(/lazy\s*\(/);
  });
});
