/**
 * Pure math helpers for panorama viewpoint positioning.
 * No Three.js dependency — testable in jsdom.
 */

import type { ViewPoint } from '../../types/canvas';

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

/**
 * Convert spherical (yaw, pitch) in degrees to Cartesian (x, y, z)
 * on a sphere of given radius.
 *
 * Convention (matches Three.js default):
 *   yaw   = rotation around Y axis (0 = -Z forward, +90 = +X right)
 *   pitch = elevation from XZ plane (+up, -down)
 */
export function sphericalToCartesian(
  yawDeg: number,
  pitchDeg: number,
  radius: number,
): { x: number; y: number; z: number } {
  const yaw = yawDeg * DEG2RAD;
  const pitch = pitchDeg * DEG2RAD;
  const cosPitch = Math.cos(pitch);
  return {
    x: radius * cosPitch * Math.sin(yaw),
    y: radius * Math.sin(pitch),
    z: -radius * cosPitch * Math.cos(yaw),
  };
}

/**
 * Inverse of sphericalToCartesian — Cartesian → (yaw, pitch) in degrees.
 */
export function cartesianToSpherical(
  x: number,
  y: number,
  z: number,
): { yaw: number; pitch: number } {
  const r = Math.sqrt(x * x + y * y + z * z);
  if (r < 1e-9) return { yaw: 0, pitch: 0 };
  const pitch = Math.asin(y / r) * RAD2DEG;
  const yaw = Math.atan2(x, -z) * RAD2DEG;
  return { yaw, pitch };
}

/**
 * Compute OrbitControls target from yaw/pitch.
 * Camera stays at origin; target is on unit sphere in the look direction.
 */
export function cameraTargetFromAngles(
  yawDeg: number,
  pitchDeg: number,
): { x: number; y: number; z: number } {
  return sphericalToCartesian(yawDeg, pitchDeg, 1);
}

/**
 * Extract current camera yaw/pitch from OrbitControls target (assumes camera at origin).
 */
export function anglesFromCameraTarget(
  tx: number,
  ty: number,
  tz: number,
): { yaw: number; pitch: number } {
  return cartesianToSpherical(tx, ty, tz);
}

/**
 * Generate hotspot data for all viewpoints except the active one.
 */
export function getOtherViewpoints(
  viewpoints: ViewPoint[],
  activeId: string | undefined,
): ViewPoint[] {
  return viewpoints.filter(vp => vp.id !== activeId);
}
