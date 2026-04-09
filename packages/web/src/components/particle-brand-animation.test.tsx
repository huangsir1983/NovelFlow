import { describe, it, expect } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';

const ANIM_PATH = path.resolve(
  process.cwd(),
  '../shared/src/components/production/canvas/ParticleBrandAnimation.tsx',
);

describe('ParticleBrandAnimation', () => {
  it('exists and exports the component', () => {
    expect(fs.existsSync(ANIM_PATH)).toBe(true);
    const source = fs.readFileSync(ANIM_PATH, 'utf8');
    expect(source).toMatch(/export const ParticleBrandAnimation/);
  });

  it('uses pure CSS animations — no Canvas, no requestAnimationFrame', () => {
    const source = fs.readFileSync(ANIM_PATH, 'utf8');
    // Must NOT use Canvas 2D or rAF (performance requirement)
    expect(source).not.toMatch(/getContext\(['"]2d['"]\)/);
    expect(source).not.toMatch(/requestAnimationFrame/);
    // Must use CSS keyframes
    expect(source).toMatch(/@keyframes/);
  });

  it('renders 虚幻造物 four characters with gold gradient', () => {
    const source = fs.readFileSync(ANIM_PATH, 'utf8');
    expect(source).toContain('虚');
    expect(source).toContain('幻');
    expect(source).toContain('造');
    expect(source).toContain('物');
    expect(source).toMatch(/background-clip:\s*text/);
    expect(source).toMatch(/gold|#ffd|#ffe|#c99/i);
  });

  it('includes shimmer sweep effect', () => {
    const source = fs.readFileSync(ANIM_PATH, 'utf8');
    expect(source).toMatch(/shimmer/i);
    expect(source).toMatch(/brand-shimmer-ltr/);
    expect(source).toMatch(/brand-shimmer-rtl/);
  });

  it('includes breathing glow / shadow layer', () => {
    const source = fs.readFileSync(ANIM_PATH, 'utf8');
    expect(source).toMatch(/brand-shadow-breathe/);
    expect(source).toMatch(/blur/);
  });

  it('uses will-change for GPU compositing', () => {
    const source = fs.readFileSync(ANIM_PATH, 'utf8');
    expect(source).toMatch(/will-change/);
  });

  it('is used in page.tsx canvas overlay with first-visit-only logic', () => {
    const pagePath = path.resolve(
      process.cwd(),
      'src/app/[locale]/projects/[id]/page.tsx',
    );
    const page = fs.readFileSync(pagePath, 'utf8');
    expect(page).toMatch(/ParticleBrandAnimation/);
    expect(page).toMatch(/canvasOverlay/);
    expect(page).toMatch(/canvasAnimPlayed/);
  });
});
