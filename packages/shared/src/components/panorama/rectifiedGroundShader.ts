/**
 * GLSL shaders for displaying the gnomonic-rectified ground texture.
 *
 * The heavy lifting (equirectangular → gnomonic reprojection) was already
 * done in the extraction pass. This shader simply samples the pre-rectified
 * texture with standard planar UV mapping and applies gamma correction.
 *
 * The ground is rendered OPAQUE — no alpha fade. It fully covers the
 * cylinder's floor area, and the cylinder walls provide the vertical context.
 */

export const rectifiedGroundVertexShader = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const rectifiedGroundFragmentShader = /* glsl */ `
  precision highp float;

  uniform sampler2D uGroundTexture;

  varying vec2 vUv;

  void main() {
    vec4 color = texture2D(uGroundTexture, vUv);

    // Three.js decodes sRGB to linear; convert back for display
    color.rgb = pow(color.rgb, vec3(1.0 / 2.2));

    gl_FragColor = vec4(color.rgb, 1.0);
  }
`;
