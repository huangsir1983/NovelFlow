/**
 * GLSL shaders for gnomonic (rectilinear) extraction of the equirectangular nadir.
 *
 * Renders a full-screen quad to a WebGLRenderTarget. Each output pixel is
 * remapped from flat (gnomonic) coordinates to equirectangular UV, producing
 * a perspective-correct floor texture free of fisheye distortion.
 *
 * Usage:
 *   1. Create a PlaneGeometry(2, 2) + ShaderMaterial with these shaders
 *   2. Render with OrthographicCamera(-1, 1, 1, -1, 0, 1) to a WebGLRenderTarget
 *   3. The resulting texture can be applied to a flat ground plane with simple UV mapping
 *
 * IMPORTANT: This shader does NOT apply gamma correction — the output is an
 * intermediate texture that will be sampled again by the ground display shader.
 */

export const gnomonicExtractVertexShader = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const gnomonicExtractFragmentShader = /* glsl */ `
  precision highp float;

  uniform sampler2D uPanorama;
  uniform float uExtent; // tan(halfFOV), controls angular coverage

  varying vec2 vUv;

  #define PI 3.14159265359
  #define TWO_PI 6.28318530718

  void main() {
    // Map UV [0,1] to normalized device coords [-1, 1]
    vec2 ndc = vUv * 2.0 - 1.0;

    // Gnomonic projection centered at nadir (-Y):
    // For pixel at (ndc.x, ndc.y), the direction on the unit sphere is:
    //   dir = normalize(ndc.x * extent, -1.0, -ndc.y * extent)
    // ndc.x → world X (right), ndc.y → world -Z (panorama forward)
    float x = ndc.x * uExtent;
    float z = -ndc.y * uExtent;

    float len = sqrt(x * x + 1.0 + z * z);
    vec3 dir = vec3(x / len, -1.0 / len, z / len);

    // Convert direction to equirectangular UV
    // (same convention as panoramaShader.ts / cylindricalShader.ts)
    float u = 0.5 + atan(dir.x, -dir.z) / TWO_PI;
    float v = 0.5 + asin(clamp(dir.y, -1.0, 1.0)) / PI;

    // Sample equirectangular panorama — NO gamma correction here
    gl_FragColor = texture2D(uPanorama, vec2(u, v));
  }
`;
