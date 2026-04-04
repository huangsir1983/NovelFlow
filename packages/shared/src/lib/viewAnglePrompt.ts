/**
 * Angle-to-prompt mapping for view angle conversion.
 * Ported from taoge/src/services/view_angle_service.py
 */

/* ── Azimuth: circular nearest-neighbor (9 entries) ── */
const AZIMUTH_MAP: [number, string][] = [
  [0, 'front view'],
  [45, 'front-right quarter view'],
  [90, 'right side view'],
  [135, 'back-right quarter view'],
  [180, 'back view'],
  [-180, 'back view'],
  [-135, 'back-left quarter view'],
  [-90, 'left side view'],
  [-45, 'front-left quarter view'],
];

/* ── Elevation: linear nearest-neighbor (4 entries) ── */
const ELEVATION_MAP: [number, string][] = [
  [-30, 'low-angle shot'],
  [0, 'eye-level shot'],
  [30, 'elevated shot'],
  [60, 'high-angle shot'],
];

/* ── Distance: threshold-based (3 segments) ── */
const DISTANCE_MAP: [number, string][] = [
  [3.3, 'close-up'],
  [6.6, 'medium shot'],
  [10.0, 'wide shot'],
];

/** Circular distance for azimuth (wraps at ±180°) */
export function nearestAzimuthText(azimuth: number): string {
  let best = 'front view';
  let minDiff = Infinity;
  for (const [angle, text] of AZIMUTH_MAP) {
    let diff = Math.abs(azimuth - angle);
    if (diff > 180) diff = 360 - diff;
    if (diff < minDiff) {
      minDiff = diff;
      best = text;
    }
  }
  return best;
}

/** Linear nearest-neighbor for elevation */
export function nearestElevationText(elevation: number): string {
  let best = 'eye-level shot';
  let minDiff = Infinity;
  for (const [angle, text] of ELEVATION_MAP) {
    const diff = Math.abs(elevation - angle);
    if (diff < minDiff) {
      minDiff = diff;
      best = text;
    }
  }
  return best;
}

/** Threshold-based distance text */
export function nearestDistanceText(distance: number): string {
  for (const [threshold, text] of DISTANCE_MAP) {
    if (distance <= threshold) return text;
  }
  return 'wide shot';
}

/**
 * Convert numeric angles to a prompt string.
 * Format: <sks> {azimuth_text} {elevation_text} {distance_text}
 * Example: <sks> front-right quarter view low-angle shot medium shot
 */
export function angleToPrompt(azimuth: number, elevation: number, distance: number): string {
  return `<sks> ${nearestAzimuthText(azimuth)} ${nearestElevationText(elevation)} ${nearestDistanceText(distance)}`;
}

/* ── Preset options for UI dropdowns ── */
export const AZIMUTH_PRESETS: { value: number; label: string }[] = [
  { value: 0, label: '正面' },
  { value: -45, label: '左前' },
  { value: 45, label: '右前' },
  { value: -90, label: '左侧' },
  { value: 90, label: '右侧' },
  { value: -135, label: '左后' },
  { value: 135, label: '右后' },
  { value: 180, label: '背面' },
];

export const ELEVATION_PRESETS: { value: number; label: string }[] = [
  { value: -30, label: '仰视' },
  { value: 0, label: '平视' },
  { value: 30, label: '俯视' },
  { value: 60, label: '高角度' },
];

export const DISTANCE_PRESETS: { value: number; label: string }[] = [
  { value: 2, label: '特写' },
  { value: 5, label: '中景' },
  { value: 8, label: '远景' },
];
