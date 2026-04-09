import { describe, it, expect } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';

const CANVAS_SYNC_PATH = path.resolve(
  process.cwd(),
  '../shared/src/hooks/useCanvasSync.ts',
);

const PAGE_PATH = path.resolve(
  process.cwd(),
  'src/app/[locale]/projects/[id]/page.tsx',
);

describe('useCanvasSync first-build optimization', () => {
  it('uses conditional debounce: immediate for first build, 100ms for subsequent', () => {
    const source = fs.readFileSync(CANVAS_SYNC_PATH, 'utf8');

    // The setTimeout call should use a conditional delay based on initializedRef
    // e.g. setTimeout(fn, initializedRef.current ? 100 : 0)
    // It should NOT always be 100ms
    const hardcoded100Only = /setTimeout\([^,]+,\s*100\s*\)/.test(source)
      && !/initializedRef\.current\s*\?\s*100\s*:\s*0/.test(source);
    expect(hardcoded100Only).toBe(false);

    // Must have the conditional pattern
    expect(source).toMatch(/initializedRef\.current\s*\?\s*100\s*:\s*0/);
  });
});

describe('ShotProductionBoard chunk prefetch', () => {
  it('page.tsx prefetches the ShotProductionBoard chunk on mount', () => {
    const source = fs.readFileSync(PAGE_PATH, 'utf8');

    // Should have a prefetch import() call for ShotProductionBoard
    // outside the dynamic() definition (e.g. in a useEffect)
    // The import path should match the dynamic() import path
    expect(source).toMatch(
      /import\(['"]@unrealmake\/shared\/components\/production\/ShotProductionBoard['"]\)/,
    );

    // There should be at least 2 occurrences of this import path:
    // 1. dynamic() definition
    // 2. prefetch call
    const matches = source.match(
      /import\(['"]@unrealmake\/shared\/components\/production\/ShotProductionBoard['"]\)/g,
    );
    expect(matches).toBeTruthy();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });
});
