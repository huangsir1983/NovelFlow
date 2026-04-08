import { describe, it, expect } from 'vitest';
import {
  sphericalToCartesian,
  cartesianToSpherical,
  cameraTargetFromAngles,
  getOtherViewpoints,
} from './panoramaHelpers';
import type { ViewPoint } from '../../types/canvas';

describe('sphericalToCartesian', () => {
  it('yaw=0, pitch=0 → negative Z (forward)', () => {
    const { x, y, z } = sphericalToCartesian(0, 0, 100);
    expect(x).toBeCloseTo(0, 5);
    expect(y).toBeCloseTo(0, 5);
    expect(z).toBeCloseTo(-100, 5);
  });

  it('yaw=90 → positive X (right)', () => {
    const { x, y, z } = sphericalToCartesian(90, 0, 100);
    expect(x).toBeCloseTo(100, 5);
    expect(y).toBeCloseTo(0, 5);
    expect(z).toBeCloseTo(0, 3);
  });

  it('pitch=90 → positive Y (up)', () => {
    const { x, y, z } = sphericalToCartesian(0, 90, 100);
    expect(x).toBeCloseTo(0, 3);
    expect(y).toBeCloseTo(100, 5);
    expect(z).toBeCloseTo(0, 3);
  });
});

describe('cartesianToSpherical', () => {
  it('forward → yaw=0, pitch=0', () => {
    const { yaw, pitch } = cartesianToSpherical(0, 0, -100);
    expect(yaw).toBeCloseTo(0, 5);
    expect(pitch).toBeCloseTo(0, 5);
  });

  it('right → yaw=90', () => {
    const { yaw, pitch } = cartesianToSpherical(100, 0, 0);
    expect(yaw).toBeCloseTo(90, 3);
    expect(pitch).toBeCloseTo(0, 5);
  });
});

describe('round-trip conversion', () => {
  const cases = [
    { yaw: 0, pitch: 0 },
    { yaw: 45, pitch: 30 },
    { yaw: -90, pitch: -45 },
    { yaw: 135, pitch: 60 },
    { yaw: -180, pitch: 0 },
  ];
  for (const { yaw, pitch } of cases) {
    it(`round-trips yaw=${yaw}, pitch=${pitch}`, () => {
      const { x, y, z } = sphericalToCartesian(yaw, pitch, 500);
      const result = cartesianToSpherical(x, y, z);
      // Handle -180/180 equivalence
      const normalizeYaw = (v: number) => ((v + 180) % 360 + 360) % 360 - 180;
      expect(normalizeYaw(result.yaw)).toBeCloseTo(normalizeYaw(yaw), 3);
      expect(result.pitch).toBeCloseTo(pitch, 3);
    });
  }
});

describe('cameraTargetFromAngles', () => {
  it('returns unit vector', () => {
    const { x, y, z } = cameraTargetFromAngles(45, 30);
    const len = Math.sqrt(x * x + y * y + z * z);
    expect(len).toBeCloseTo(1, 5);
  });
});

describe('getOtherViewpoints', () => {
  const vps: ViewPoint[] = [
    { id: 'a', label: 'A', yaw: 0, pitch: 0, fov: 75, isDefault: true },
    { id: 'b', label: 'B', yaw: 90, pitch: 0, fov: 60 },
    { id: 'c', label: 'C', yaw: -90, pitch: 0, fov: 50 },
  ];

  it('excludes active viewpoint', () => {
    const others = getOtherViewpoints(vps, 'a');
    expect(others).toHaveLength(2);
    expect(others.map(v => v.id)).toEqual(['b', 'c']);
  });

  it('returns all when no active', () => {
    const others = getOtherViewpoints(vps, undefined);
    expect(others).toHaveLength(3);
  });
});
