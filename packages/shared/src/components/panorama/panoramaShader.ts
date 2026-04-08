/**
 * Custom GLSL shaders for equirectangular panorama rendering with distortion correction.
 *
 * When the camera moves off-center inside the panorama sphere, the standard UV mapping
 * produces non-linear distortion (stretching near the camera, compression far away).
 *
 * The correction blends between:
 *   - sphereDir: direction from origin → full parallax + full distortion
 *   - rayDir: direction from camera → no parallax, no distortion
 *
 * uCorrectionStrength controls the blend (0 = raw, 0.5 = balanced, 1 = fully corrected).
 */

export const panoramaVertexShader = /* glsl */ `
  varying vec3 vWorldPos;

  void main() {
    vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const panoramaFragmentShader = /* glsl */ `
  precision highp float;

  uniform sampler2D uPanorama;
  uniform vec3 uCameraOffset;
  uniform float uCorrectionStrength;

  varying vec3 vWorldPos;

  #define PI 3.14159265359
  #define TWO_PI 6.28318530718

  void main() {
    vec3 sphereDir = normalize(vWorldPos);
    vec3 rayDir = normalize(vWorldPos - uCameraOffset);

    // Blend between distorted (sphere) and corrected (ray) directions
    vec3 dir = normalize(mix(sphereDir, rayDir, uCorrectionStrength));

    // Convert direction to equirectangular UV
    float u = 0.5 + atan(dir.x, -dir.z) / TWO_PI;
    float v = 0.5 + asin(clamp(dir.y, -1.0, 1.0)) / PI;

    vec4 color = texture2D(uPanorama, vec2(u, v));
    // Three.js decodes sRGB texture to linear; convert back for display
    color.rgb = pow(color.rgb, vec3(1.0 / 2.2));
    gl_FragColor = color;
  }
`;
