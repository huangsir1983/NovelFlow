import { describe, it, expect } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';

const SRC_PATH = path.resolve(
  process.cwd(),
  '../shared/src/components/production/canvas/ImageProcessNode.tsx',
);

describe('ImageProcessNode upstream image extraction', () => {
  const source = fs.readFileSync(SRC_PATH, 'utf8');

  it('should include visualRefUrl in the URL fallback chain for upstream images', () => {
    // The upstreamImages useMemo extracts URLs from upstream node data.
    // CharacterProcess nodes store their reference image in `visualRefUrl`,
    // so the URL extraction must include it — otherwise 图1 won't display.
    const urlLine = source
      .split('\n')
      .find(l => l.includes('outputImageUrl') && l.includes('as string'));
    expect(urlLine).toBeDefined();
    expect(urlLine).toContain('visualRefUrl');
  });

  it('should already include visualRefStorageKey in the storageKey fallback chain', () => {
    const keyLine = source
      .split('\n')
      .find(l => l.includes('outputStorageKey') && l.includes('as string'));
    expect(keyLine).toBeDefined();
    expect(keyLine).toContain('visualRefStorageKey');
  });
});
