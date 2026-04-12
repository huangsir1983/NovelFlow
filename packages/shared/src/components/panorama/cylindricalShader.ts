/**
 * GLSL shaders for cylindrical panorama projection.
 *
 * Maps an equirectangular panorama onto a cylinder without the polar distortion
 * inherent in spherical projection. Vertical lines in the real scene appear straight
 * on the cylinder walls.
 *
 * Mapping:
 *   u = horizontal angle (same as equirectangular longitude)
 *   v = atan((y - eyeLevel) / radius) → equivalent spherical latitude
 */

export const cylinderVertexShader = /* glsl */ `
  varying vec3 vWorldPos;

  void main() {
    vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const cylinderFragmentShader = /* glsl */ `
  precision highp float;

  uniform sampler2D uPanorama;
  uniform float uCylinderRadius;
  uniform float uEyeLevel;

  varying vec3 vWorldPos;

  #define PI 3.14159265359
  #define TWO_PI 6.28318530718

  void main() {
    // Horizontal angle — matches equirectangular longitude convention
    float theta = atan(vWorldPos.x, -vWorldPos.z);
    float u = 0.5 + theta / TWO_PI;

    // Vertical: height above eye level → equivalent spherical latitude
    // atan gives correct cylindrical-to-equirectangular conversion
    float latitude = atan(vWorldPos.y - uEyeLevel, uCylinderRadius);
    float v = 0.5 + latitude / PI;

    vec4 color = texture2D(uPanorama, vec2(u, v));
    // Three.js decodes sRGB to linear; convert back for display
    color.rgb = pow(color.rgb, vec3(1.0 / 2.2));
    gl_FragColor = color;
  }
`;

/**
 * Ground plane shaders — project the panorama nadir onto the floor.
 *
 * For each floor point at horizontal distance d from center:
 *   direction = (x, -eyeLevel, z)  → looking down from panorama origin
 *   latitude  = atan(-eyeLevel, d) → always negative (downward)
 *
 * At the floor edge (d = R), this produces the SAME v as the cylinder
 * wall at y = 0, giving a seamless visual transition.
 */

export const groundVertexShader = /* glsl */ `
  varying vec3 vWorldPos;

  void main() {
    vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const groundFragmentShader = /* glsl */ `
  precision highp float;

  uniform sampler2D uPanorama;
  uniform float uEyeLevel;
  uniform float uGroundRadius;

  varying vec3 vWorldPos;

  #define PI 3.14159265359
  #define TWO_PI 6.28318530718

  void main() {
    float dist = length(vWorldPos.xz);

    // Horizontal angle — same convention as cylinder walls
    float theta = atan(vWorldPos.x, -vWorldPos.z);
    float u = 0.5 + theta / TWO_PI;

    // Looking down from eye level to floor at distance dist
    float latitude = atan(-uEyeLevel, max(dist, 0.001));
    float v = 0.5 + latitude / PI;

    vec4 panoColor = texture2D(uPanorama, vec2(u, v));
    panoColor.rgb = pow(panoColor.rgb, vec3(1.0 / 2.2));

    // Neutral dark floor base
    vec3 darkFloor = vec3(0.06, 0.06, 0.08);

    // Blend based on viewing angle: shallow angles (near wall) → panorama,
    // steep angles (near nadir/center) → dark floor to avoid distortion.
    // angularDepth: 0.0 = horizon, 1.0 = straight down (nadir)
    float angularDepth = -latitude / (PI * 0.5);
    // Show panorama only where angle < ~25° below horizon (angularDepth < 0.28)
    // Fully dark beyond ~45° (angularDepth > 0.5)
    float panoMix = 1.0 - smoothstep(0.22, 0.50, angularDepth);

    vec3 finalColor = mix(darkFloor, panoColor.rgb * 0.85, panoMix);

    gl_FragColor = vec4(finalColor, 1.0);
  }
`;
