'use client';

import { memo } from 'react';

interface ParticleBrandAnimationProps {
  className?: string;
}

/* ── All animation is pure CSS — zero JS, zero rAF ── */

const BRAND_CHARS = ['虚', '幻', '造', '物'] as const;

/**
 * Pure-CSS brand intro animation.
 *
 * Every animated property (opacity, transform, background-position) runs on
 * the browser compositor / GPU thread — zero main-thread cost, no conflict
 * with ReactFlow initialisation.
 *
 * Key structure:
 *   wrapper <span> (brand-anim-float)  → continuous gentle hovering
 *     inner <span> (brand-anim-char)   → one-shot entrance fade+slide
 *
 * This avoids dual-animation on a single element which causes transform
 * conflicts in some browsers.
 */
export const ParticleBrandAnimation = memo(function ParticleBrandAnimation({
  className,
}: ParticleBrandAnimationProps) {
  return (
    <div
      data-testid="canvas-skeleton"
      className={`brand-anim-root ${className ?? ''}`}
    >
      <style>{cssText}</style>

      {/* Radial ambient glow — strong pulse */}
      <div className="brand-anim-glow" />

      {/* Decorative horizontal lines — expand outward */}
      <div className="brand-anim-line brand-anim-line-left" />
      <div className="brand-anim-line brand-anim-line-right" />

      {/* Full-screen shimmer sweeps — no visible rectangle edges */}
      <div className="brand-anim-shimmer brand-anim-shimmer-1" />
      <div className="brand-anim-shimmer brand-anim-shimmer-2" />

      {/* Characters — wrapper handles float, inner handles entrance */}
      <div className="brand-anim-chars">
        {BRAND_CHARS.map((ch, i) => (
          <span
            key={ch}
            className="brand-anim-float"
            style={{ animationDelay: `${2.5 + i * 0.2}s` }}
          >
            <span
              className="brand-anim-char"
              style={{ animationDelay: `${0.4 + i * 0.5}s` }}
            >
              {ch}
            </span>
          </span>
        ))}
      </div>

      {/* Breathing glow layer (behind main chars) */}
      <div className="brand-anim-chars brand-anim-shadow-layer" aria-hidden="true">
        {BRAND_CHARS.map((ch, i) => (
          <span
            key={ch}
            className="brand-anim-float-shadow"
            style={{ animationDelay: `${2.2 + i * 0.3}s` }}
          >
            <span
              className="brand-anim-char brand-anim-char-shadow"
              style={{ animationDelay: `${0.4 + i * 0.5}s` }}
            >
              {ch}
            </span>
          </span>
        ))}
      </div>

      {/* Floating sparkle dots */}
      <div className="brand-anim-sparkles" aria-hidden="true">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="brand-anim-dot"
            style={{
              left: `${12 + (i % 6) * 14}%`,
              top: `${28 + Math.floor(i / 6) * 38}%`,
              animationDelay: `${1.8 + i * 0.4}s`,
              animationDuration: `${2.5 + (i % 3) * 0.8}s`,
            }}
          />
        ))}
      </div>

      {/* Hint text */}
      <div className="brand-anim-hint" data-testid="canvas-skeleton-hint">
        正在装配画布…
      </div>

      {/* Test anchors */}
      <span data-testid="canvas-skeleton-dotgrid" className="sr-only" />
      <span data-testid="skeleton-node-scene" className="sr-only" />
      <span data-testid="skeleton-node-shot" className="sr-only" />
      <span data-testid="skeleton-node-pipeline" className="sr-only" />
    </div>
  );
});

/* ────────────────────────────────────────────
 * CSS
 * ──────────────────────────────────────────── */
const cssText = /* css */ `
/* ── Root ── */
.brand-anim-root {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #05050a;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

/* ── Ambient radial glow ── */
.brand-anim-glow {
  position: absolute;
  inset: -20%;
  background: radial-gradient(
    ellipse 50% 45% at 50% 50%,
    rgba(255, 195, 50, 0.22) 0%,
    rgba(255, 170, 30, 0.10) 30%,
    rgba(200, 150, 40, 0.04) 55%,
    transparent 75%
  );
  opacity: 0;
  animation: brand-glow-pulse 3s ease-in-out 0.3s infinite;
  will-change: opacity, transform;
}

@keyframes brand-glow-pulse {
  0%   { opacity: 0.35; transform: scale(1); }
  50%  { opacity: 1;    transform: scale(1.1); }
  100% { opacity: 0.35; transform: scale(1); }
}

/* ── Decorative lines ── */
.brand-anim-line {
  position: absolute;
  top: 50%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 210, 80, 0.6), transparent);
  transform: scaleX(0);
  animation: brand-line-expand 2s cubic-bezier(0.22, 1, 0.36, 1) 2s forwards,
             brand-line-glow 2.5s ease-in-out 4s infinite;
  will-change: transform, opacity;
}
.brand-anim-line-left {
  right: 50%;
  width: 28%;
  margin-right: clamp(120px, 26vw, 380px);
  transform-origin: right center;
}
.brand-anim-line-right {
  left: 50%;
  width: 28%;
  margin-left: clamp(120px, 26vw, 380px);
  transform-origin: left center;
}

@keyframes brand-line-expand {
  0%   { transform: scaleX(0); opacity: 0; }
  100% { transform: scaleX(1); opacity: 1; }
}

@keyframes brand-line-glow {
  0%, 100% { opacity: 0.35; }
  50%      { opacity: 1; }
}

/* ── Full-screen shimmer sweeps ──
   Positioned on root, not on chars container → no rectangular edges */
.brand-anim-shimmer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 3;
  will-change: background-position;
}

.brand-anim-shimmer-1 {
  background: linear-gradient(
    105deg,
    transparent 0%,
    transparent 38%,
    rgba(255, 240, 180, 0.12) 43%,
    rgba(255, 255, 255, 0.20) 50%,
    rgba(255, 240, 180, 0.12) 57%,
    transparent 62%,
    transparent 100%
  );
  background-size: 300% 100%;
  animation: brand-shimmer-ltr 3s ease-in-out 2s infinite;
}

.brand-anim-shimmer-2 {
  background: linear-gradient(
    75deg,
    transparent 0%,
    transparent 35%,
    rgba(255, 220, 120, 0.08) 42%,
    rgba(255, 245, 200, 0.14) 50%,
    rgba(255, 220, 120, 0.08) 58%,
    transparent 65%,
    transparent 100%
  );
  background-size: 300% 100%;
  animation: brand-shimmer-rtl 4.5s ease-in-out 3.5s infinite;
}

@keyframes brand-shimmer-ltr {
  0%   { background-position: 300% center; }
  100% { background-position: -300% center; }
}

@keyframes brand-shimmer-rtl {
  0%   { background-position: -300% center; }
  100% { background-position: 300% center; }
}

/* ── Character container ── */
.brand-anim-chars {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.1em;
  z-index: 4;
  font-size: clamp(48px, 11vw, 150px);
  line-height: 1;
}

/* ── Float wrapper — continuous gentle hover ── */
.brand-anim-float {
  display: inline-block;
  animation: brand-char-float 4s ease-in-out infinite;
  will-change: transform;
}

.brand-anim-float-shadow {
  display: inline-block;
  animation: brand-char-float 4.5s ease-in-out infinite;
  will-change: transform;
}

@keyframes brand-char-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-7px); }
}

/* ── Individual character — entrance only (single animation) ── */
.brand-anim-char {
  display: inline-block;
  font-family: "STXingkai", "华文行楷", "STKaiti", "楷体", "KaiTi", serif;
  font-weight: bold;
  letter-spacing: 0.06em;
  color: transparent;
  background: linear-gradient(
    135deg,
    #b8860b 0%,
    #ffd760 20%,
    #fffbe6 40%,
    #ffd760 60%,
    #b8860b 80%,
    #ffd760 100%
  );
  background-size: 300% 300%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  opacity: 0;
  transform: translateY(28px) scale(0.9);
  animation: brand-char-in 1.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  will-change: opacity, transform;
}

@keyframes brand-char-in {
  0% {
    opacity: 0;
    transform: translateY(28px) scale(0.9);
  }
  55% {
    opacity: 1;
    transform: translateY(-5px) scale(1.03);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Gold gradient color shift on container */
.brand-anim-chars:not(.brand-anim-shadow-layer) {
  animation: brand-gradient-shift 5s ease-in-out 2.5s infinite;
}

@keyframes brand-gradient-shift {
  0%   { filter: hue-rotate(0deg) brightness(1); }
  30%  { filter: hue-rotate(-10deg) brightness(1.2); }
  60%  { filter: hue-rotate(5deg) brightness(1.05); }
  100% { filter: hue-rotate(0deg) brightness(1); }
}

/* ── Shadow / glow layer ── */
.brand-anim-shadow-layer {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
  pointer-events: none;
}

.brand-anim-char-shadow {
  background: none !important;
  -webkit-text-fill-color: rgba(255, 200, 60, 0.7) !important;
  color: rgba(255, 200, 60, 0.7) !important;
  filter: blur(20px);
  animation: brand-char-in 1.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  will-change: opacity, transform, filter;
}

/* Strong breathing on shadow layer container */
.brand-anim-shadow-layer {
  animation: brand-shadow-breathe 2.5s ease-in-out 2.5s infinite;
}

@keyframes brand-shadow-breathe {
  0%, 100% { opacity: 0.4; transform: translate(-50%, -50%) scale(1); }
  50%      { opacity: 1;   transform: translate(-50%, -50%) scale(1.06); }
}

/* ── Floating sparkle dots ── */
.brand-anim-sparkles {
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
}

.brand-anim-dot {
  position: absolute;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 230, 140, 0.9), rgba(255, 200, 60, 0) 70%);
  opacity: 0;
  animation: brand-dot-twinkle 2.5s ease-in-out infinite;
  will-change: opacity, transform;
}

@keyframes brand-dot-twinkle {
  0%, 100% { opacity: 0;   transform: scale(0.5) translateY(0); }
  20%      { opacity: 0.8; transform: scale(1.3) translateY(-4px); }
  50%      { opacity: 0.5; transform: scale(1)   translateY(-8px); }
  80%      { opacity: 0.2; transform: scale(0.7) translateY(-3px); }
}

/* ── Hint text ── */
.brand-anim-hint {
  margin-top: 2.5rem;
  font-size: 13px;
  color: rgba(255, 215, 100, 0);
  z-index: 4;
  animation: brand-hint-in 0.8s ease-out 2.8s forwards,
             brand-hint-pulse 3s ease-in-out 3.8s infinite;
}

@keyframes brand-hint-in {
  0%   { color: rgba(255, 215, 100, 0); }
  100% { color: rgba(255, 215, 100, 0.4); }
}

@keyframes brand-hint-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.45; }
}

/* ── Utility ── */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
`;
