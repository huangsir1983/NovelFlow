/**
 * Pure math for gnomonic (rectilinear) projection of the equirectangular nadir.
 *
 * Gnomonic projection maps a region of the unit sphere onto a tangent plane.
 * Here we project from the nadir (straight down, -Y) so the result is a
 * perspective-correct floor texture that can be applied to a flat ground plane
 * with simple planar UV mapping — no fisheye distortion.
 *
 * No Three.js dependency — fully unit-testable.
 */

const PI = Math.PI;
const TWO_PI = 2 * PI;

/**
 * Default ground FOV in degrees.
 * 140° → extent ≈ 2.75, covers from nadir to ~20° below horizon.
 */
export const DEFAULT_GROUND_FOV = 140;

/**
 * Convert a FOV angle (in degrees) to the gnomonic extent parameter.
 * extent = tan(fov / 2)
 */
export function fovToExtent(fovDegrees: number): number {
  return Math.tan((fovDegrees * PI) / 360);
}

/**
 * Map a normalized pixel coordinate on the gnomonic output texture
 * to equirectangular UV coordinates.
 *
 * @param px - Horizontal position in [-1, 1] (left to right)
 * @param py - Vertical position in [-1, 1] (bottom to top)
 * @param extent - tan(halfFOV), controls angular coverage
 * @returns {u, v} in [0, 1] for sampling the equirectangular panorama
 *
 * Convention (matches panoramaShader.ts):
 *   u = 0.5 + atan(dir.x, -dir.z) / (2π)   — longitude
 *   v = 0.5 + asin(dir.y) / π               — latitude (v=0 nadir, v=1 zenith)
 *
 * The gnomonic projection is centered at nadir (-Y). For pixel (px, py):
 *   dir = normalize(px * extent, -1, -py * extent)
 *
 * px maps to world X (right), py maps to world -Z (forward in panorama convention).
 */
export function gnomonicNadirToEquirectUV(
  px: number,
  py: number,
  extent: number,
): { u: number; v: number } {
  const x = px * extent;
  const y = -1;
  const z = -py * extent;

  const len = Math.sqrt(x * x + y * y + z * z);
  const dx = x / len;
  const dy = y / len;
  const dz = z / len;

  // Equirectangular UV (same convention as panoramaShader.ts)
  const u = 0.5 + Math.atan2(dx, -dz) / TWO_PI;
  const v = 0.5 + Math.asin(Math.max(-1, Math.min(1, dy))) / PI;

  return { u, v };
}
