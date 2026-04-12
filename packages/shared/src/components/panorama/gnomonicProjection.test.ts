import { describe, it, expect } from 'vitest';
import {
  gnomonicNadirToEquirectUV,
  fovToExtent,
  DEFAULT_GROUND_FOV,
} from './gnomonicProjection';

describe('fovToExtent', () => {
  it('90° FOV → extent = 1.0 (tan 45°)', () => {
    expect(fovToExtent(90)).toBeCloseTo(1.0, 6);
  });

  it('180° FOV → extent = very large (tan 90° → Infinity)', () => {
    expect(fovToExtent(180)).toBeGreaterThan(1e10);
  });

  it('60° FOV → extent = tan(30°) ≈ 0.577', () => {
    expect(fovToExtent(60)).toBeCloseTo(Math.tan(Math.PI / 6), 6);
  });

  it('DEFAULT_GROUND_FOV (140°) → extent ≈ 2.747', () => {
    expect(fovToExtent(DEFAULT_GROUND_FOV)).toBeCloseTo(
      Math.tan((140 * Math.PI) / 360),
      3,
    );
  });
});

describe('gnomonicNadirToEquirectUV', () => {
  const PI = Math.PI;

  it('center (0,0) maps to nadir: v ≈ 0', () => {
    const { v } = gnomonicNadirToEquirectUV(0, 0, 1);
    // dir = normalize(0, -1, 0) → straight down → asin(-1)/π + 0.5 = 0
    expect(v).toBeCloseTo(0, 6);
  });

  it('center (0,0) maps to u = 0.5 (atan2(0, 0) is 0)', () => {
    const { u } = gnomonicNadirToEquirectUV(0, 0, 1);
    // dir.x = 0, dir.z = 0 → atan2(0, 0) = 0 → u = 0.5
    expect(u).toBeCloseTo(0.5, 6);
  });

  it('edge (1, 0) with extent=1 → latitude = -45°, v = 0.25', () => {
    // dir = normalize(1, -1, 0) = (1/√2, -1/√2, 0)
    // asin(-1/√2) = -π/4 → v = 0.5 + (-π/4)/π = 0.25
    const { v } = gnomonicNadirToEquirectUV(1, 0, 1);
    expect(v).toBeCloseTo(0.25, 5);
  });

  it('edge (-1, 0) with extent=1 → same latitude, v = 0.25', () => {
    const { v } = gnomonicNadirToEquirectUV(-1, 0, 1);
    expect(v).toBeCloseTo(0.25, 5);
  });

  it('edge (0, 1) with extent=1 → latitude = -45°, v = 0.25', () => {
    // dir = normalize(0, -1, -1) = (0, -1/√2, -1/√2)
    const { v } = gnomonicNadirToEquirectUV(0, 1, 1);
    expect(v).toBeCloseTo(0.25, 5);
  });

  it('u symmetry: fn(px, py).u and fn(-px, py).u are symmetric around 0.5', () => {
    // Negating only px flips dir.x → atan2 negates → u mirrors around 0.5
    const a = gnomonicNadirToEquirectUV(0.5, 0.3, 2.0);
    const b = gnomonicNadirToEquirectUV(-0.5, 0.3, 2.0);
    expect(a.u + b.u).toBeCloseTo(1.0, 5);
  });

  it('v symmetry: opposite pixels have same latitude (v)', () => {
    const a = gnomonicNadirToEquirectUV(0.7, 0.4, 1.5);
    const b = gnomonicNadirToEquirectUV(-0.7, -0.4, 1.5);
    expect(a.v).toBeCloseTo(b.v, 6);
  });

  it('all v values are in [0, 0.5] (nadir hemisphere)', () => {
    // Gnomonic nadir projection always looks downward → latitude ≤ 0 → v ≤ 0.5
    const testPoints = [
      [0, 0], [1, 0], [0, 1], [-1, 0], [0, -1],
      [0.5, 0.5], [-0.8, 0.3], [0.9, -0.9],
    ];
    for (const [px, py] of testPoints) {
      const { v } = gnomonicNadirToEquirectUV(px, py, 2.75);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(0.5);
    }
  });

  it('larger extent covers more area (higher v near edges)', () => {
    // Same pixel position, larger extent → looks further from nadir → higher v
    const small = gnomonicNadirToEquirectUV(0.8, 0, 1.0);
    const large = gnomonicNadirToEquirectUV(0.8, 0, 2.75);
    expect(large.v).toBeGreaterThan(small.v);
  });

  it('u values wrap correctly: right edge → u > 0.5, left edge → u < 0.5', () => {
    // px > 0 → dir.x > 0 → atan2(+, -dz) with dz=0 → π/2 → u > 0.5
    const right = gnomonicNadirToEquirectUV(1, 0, 1);
    expect(right.u).toBeGreaterThan(0.5);

    const left = gnomonicNadirToEquirectUV(-1, 0, 1);
    expect(left.u).toBeLessThan(0.5);
  });

  it('forward direction (py=1) maps to u ≈ 0.5 (looking along -Z)', () => {
    // dir = normalize(0, -1, -extent) → dir.x = 0 → atan2(0, extent/len) → 0 → u = 0.5
    const { u } = gnomonicNadirToEquirectUV(0, 1, 2);
    expect(u).toBeCloseTo(0.5, 5);
  });

  it('known angle: extent=tan(70°), edge (1,0) → latitude ≈ -20°', () => {
    // At edge with extent=tan(70°), the angular distance from nadir is 70°
    // latitude = -(90° - 70°) = -20° → v = 0.5 + (-20/180) ≈ 0.389
    const extent = Math.tan((70 * PI) / 180);
    const { v } = gnomonicNadirToEquirectUV(1, 0, extent);
    const expectedV = 0.5 + (-20 / 180);
    expect(v).toBeCloseTo(expectedV, 3);
  });
});
