'use client';

import { useRef, useEffect, useCallback, memo } from 'react';

/* ── Geometry constants (from taoge view_angle_widget.py) ── */
const BASE_W = 320;
const BASE_H = 300; // canvas area (excluding bottom text)

const RING_RX = 140;
const RING_RY = 50;
const RING_CY_OFFSET = 10;
const AZ_RENDER_OFFSET = 30;

const ELEV_RX = 70;
const ELEV_RY = 120;
const ELEV_ARC_CX_OFF = -10;
const ELEV_RENDER_OFFSET = -10;

const DIST_SCALE_MIN = 0.15;
const DIST_SCALE_MAX = 0.92;

const HIT_RADIUS = 20;
const HANDLE_R = 8;

/* ── 3D projection constants (from taoge) ── */
const AZ_NONLINEAR_OFFSET = 35;
const FOCAL = 450;
const CAM_DEPTH_BASE = 300;
const CAM_DEPTH_DIST_SCALE = 30;
const IMAGE_SIZE = 200;
const IMG_CY_OFFSET = -35; // image center above ring center

/* ── Colors ── */
const COL_AZ = 'rgb(255,100,150)';
const COL_EL = 'rgb(80,220,220)';
const COL_DIST = 'rgb(240,200,80)';
const COL_TXT = 'rgba(255,255,255,0.7)';

type DragTarget = 'azimuth' | 'elevation' | 'distance' | null;

interface ViewAngleCanvasProps {
  width: number;
  height: number;
  azimuth: number;
  elevation: number;
  distance: number;
  previewImageUrl?: string;
  onChange: (azimuth: number, elevation: number, distance: number) => void;
}

/* ── Helper: lerp between two 2D points ── */
function lerpPt(a: [number, number], b: [number, number], t: number): [number, number] {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

function ViewAngleCanvasComponent({
  width,
  height,
  azimuth,
  elevation,
  distance,
  previewImageUrl,
  onChange,
}: ViewAngleCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef<DragTarget>(null);

  const sx = width / BASE_W;
  const sy = (height - 40) / BASE_H; // reserve 40px for bottom text
  const s = Math.min(sx, sy);

  // Ring center
  const rcx = width / 2;
  const rcy = height / 2 - 20 + RING_CY_OFFSET * s;

  // Scale geometry
  const ringRx = RING_RX * s;
  const ringRy = RING_RY * s;
  const elevRx = ELEV_RX * s;
  const elevRy = ELEV_RY * s;

  /* ── Angle conversion helpers ── */
  const azToRender = useCallback((az: number) => {
    return (90 - az + AZ_RENDER_OFFSET) * Math.PI / 180;
  }, []);

  const azHandlePos = useCallback((az: number): [number, number] => {
    const a = azToRender(az);
    return [rcx + ringRx * Math.cos(a), rcy + ringRy * Math.sin(a)];
  }, [azToRender, rcx, rcy, ringRx, ringRy]);

  const distHandlePos = useCallback((az: number, dist: number): [number, number] => {
    const a = azToRender(az);
    const t = dist / 10;
    const sc = DIST_SCALE_MIN + t * (DIST_SCALE_MAX - DIST_SCALE_MIN);
    return [rcx + sc * ringRx * Math.cos(a), rcy + sc * ringRy * Math.sin(a)];
  }, [azToRender, rcx, rcy, ringRx, ringRy]);

  const elevHandlePos = useCallback((el: number): [number, number] => {
    const arcCx = rcx + ELEV_ARC_CX_OFF * s;
    const arcCy = rcy - 20 * s;
    const e = (el + ELEV_RENDER_OFFSET) * Math.PI / 180;
    return [arcCx - elevRx * Math.cos(e), arcCy - elevRy * Math.sin(e)];
  }, [rcx, rcy, s, elevRx, elevRy]);

  /* ── Load preview image ── */
  useEffect(() => {
    if (!previewImageUrl) { imgRef.current = null; return; }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => { imgRef.current = img; };
    img.src = previewImageUrl;
  }, [previewImageUrl]);

  /* ── Draw ── */
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    /* 1. Azimuth ring — back half (top semicircle = further from viewer, dimmed) */
    ctx.save();
    ctx.strokeStyle = COL_AZ;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.4; // 100/255 ≈ 0.4 like taoge
    ctx.beginPath();
    // 180° to 360° = top semicircle (left → top → right)
    ctx.ellipse(rcx, rcy, ringRx, ringRy, 0, Math.PI, 2 * Math.PI);
    ctx.stroke();
    ctx.restore();

    /* 2. Center preview image with TRUE 3D perspective projection */
    paintPreview(ctx);

    /* 3. Azimuth ring — front half (bottom semicircle = closer to viewer, bright) */
    ctx.save();
    ctx.strokeStyle = COL_AZ;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    // 0° to 180° = bottom semicircle (right → bottom → left)
    ctx.ellipse(rcx, rcy, ringRx, ringRy, 0, 0, Math.PI);
    ctx.stroke();
    ctx.restore();

    /* 4. Elevation arc — from -50° to +80° like taoge */
    ctx.save();
    const arcCx = rcx + ELEV_ARC_CX_OFF * s;
    const arcCy = rcy - 20 * s;
    ctx.strokeStyle = COL_EL;
    ctx.lineWidth = 2;
    ctx.beginPath();
    const arcStart = -50;
    const arcEnd = 80;
    for (let i = 0; i <= 120; i++) {
      const theta = (arcStart + i * (arcEnd - arcStart) / 120) * Math.PI / 180;
      const px = arcCx - elevRx * Math.cos(theta);
      const py = arcCy - elevRy * Math.sin(theta);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();
    ctx.restore();

    /* 5. Distance line */
    ctx.save();
    const azA = azToRender(azimuth);
    const cosA = Math.cos(azA);
    const sinA = Math.sin(azA);
    const x1 = rcx + DIST_SCALE_MIN * ringRx * cosA;
    const y1 = rcy + DIST_SCALE_MIN * ringRy * sinA;
    const x2 = rcx + DIST_SCALE_MAX * ringRx * cosA;
    const y2 = rcy + DIST_SCALE_MAX * ringRy * sinA;
    ctx.strokeStyle = COL_DIST;
    ctx.lineWidth = 2.5;
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.restore();

    /* 6. Handle dots with glow + white border (matching taoge) */
    const drawHandle = (x: number, y: number, col: string) => {
      // Parse rgb from string for gradient
      const rgbMatch = col.match(/(\d+),(\d+),(\d+)/);
      const [r, g, b] = rgbMatch ? [+rgbMatch[1], +rgbMatch[2], +rgbMatch[3]] : [255, 255, 255];

      // Glow halo (radius = HANDLE_R * 2.5)
      const glowR = HANDLE_R * 2.5 * s;
      const grad = ctx.createRadialGradient(x, y, 0, x, y, glowR);
      grad.addColorStop(0, `rgba(${r},${g},${b},0.63)`);  // 160/255 ≈ 0.63
      grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(x, y, glowR, 0, 2 * Math.PI);
      ctx.fill();

      // Solid dot with white border
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(x, y, HANDLE_R * s, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    };

    const [ex, ey] = elevHandlePos(elevation);
    const [dx, dy] = distHandlePos(azimuth, distance);
    const [ax, ay] = azHandlePos(azimuth);
    drawHandle(ex, ey, COL_EL);
    drawHandle(dx, dy, COL_DIST);
    drawHandle(ax, ay, COL_AZ);

    /* 7. Bottom text */
    const textY = height - 15;
    ctx.font = `${11 * s}px system-ui, sans-serif`;
    ctx.textAlign = 'center';

    const col3W = width / 3;
    ctx.fillStyle = COL_TXT;
    ctx.fillText('水平角度', col3W * 0.5, textY - 16 * s);
    ctx.fillText('垂直角度', col3W * 1.5, textY - 16 * s);
    ctx.fillText('距离', col3W * 2.5, textY - 16 * s);
    ctx.font = `bold ${13 * s}px system-ui, sans-serif`;
    ctx.fillStyle = COL_AZ;
    ctx.fillText(`${azimuth.toFixed(0)}°`, col3W * 0.5, textY);
    ctx.fillStyle = COL_EL;
    ctx.fillText(`${elevation.toFixed(0)}°`, col3W * 1.5, textY);
    ctx.fillStyle = COL_DIST;
    ctx.fillText(distance.toFixed(1), col3W * 2.5, textY);

    /* ── 3D perspective preview rendering (ported from taoge _paint_preview) ── */
    function paintPreview(ctx: CanvasRenderingContext2D) {
      const imgCx = rcx;
      const imgCy = rcy + IMG_CY_OFFSET * s;

      if (!imgRef.current) {
        // Placeholder rect
        ctx.save();
        ctx.fillStyle = 'rgba(255,255,255,0.05)';
        const pw = 60 * s;
        const ph = 80 * s;
        ctx.fillRect(imgCx - pw / 2, imgCy - ph / 2, pw, ph);
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(imgCx - pw / 2, imgCy - ph / 2, pw, ph);
        ctx.setLineDash([]);
        ctx.restore();
        return;
      }

      const img = imgRef.current;

      // Scale image to IMAGE_SIZE maintaining aspect ratio
      const imgNatW = img.naturalWidth;
      const imgNatH = img.naturalHeight;
      const maxDim = IMAGE_SIZE * s;
      const imgScale = Math.min(maxDim / imgNatW, maxDim / imgNatH);
      const w = imgNatW * imgScale;
      const h = imgNatH * imgScale;
      const hw = w / 2;
      const hh = h / 2;

      // ── Non-linear azimuth mapping ──
      // In our convention: negative azimuth = camera to the LEFT = see character's LEFT side
      // = RIGHT side of front-view image should be closer to camera
      // Flip sign vs taoge's PyQt convention to match our camera-position convention
      let effectiveDeg = azimuth + AZ_NONLINEAR_OFFSET * Math.cos(azimuth * Math.PI / 180);

      // ── Mirror flip past ±90° ──
      let mirror = false;
      if (effectiveDeg > 90) { mirror = true; effectiveDeg -= 180; }
      else if (effectiveDeg < -90) { mirror = true; effectiveDeg += 180; }

      const azRad = effectiveDeg * Math.PI / 180;
      const elRad = (elevation * 0.5 + 20) * Math.PI / 180; // dampened + 20° baseline

      // ── Virtual camera ──
      const focal = FOCAL * s;
      const camDepth = (CAM_DEPTH_BASE + distance * CAM_DEPTH_DIST_SCALE) * s;

      // ── Project 4 corners: TL, TR, BR, BL ──
      const corners: [number, number][] = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]];
      const projected: [number, number][] = corners.map(([cx3, cy3]) => {
        // Y-axis rotation (azimuth — horizontal spin)
        const x1 = cx3 * Math.cos(azRad);
        const y1 = cy3;
        const z1 = cx3 * Math.sin(azRad);

        // X-axis rotation (elevation — tilt)
        const x2 = x1;
        const y2 = y1 * Math.cos(elRad) - z1 * Math.sin(elRad);
        const z2 = y1 * Math.sin(elRad) + z1 * Math.cos(elRad);

        // Perspective projection (pinhole camera)
        const zFinal = Math.max(z2 + camDepth, 1);
        return [x2 * focal / zFinal + imgCx, y2 * focal / zFinal + imgCy];
      });

      // ── Draw shadow (projected quad offset by 3px) ──
      const shadowOff = 3 * s;
      ctx.save();
      ctx.fillStyle = 'rgba(0,0,0,0.2)';
      ctx.beginPath();
      ctx.moveTo(projected[0][0] + shadowOff, projected[0][1] + shadowOff);
      for (let i = 1; i < 4; i++) ctx.lineTo(projected[i][0] + shadowOff, projected[i][1] + shadowOff);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      // ── Draw background pad (slightly larger) ──
      const pad = 3 * s;
      ctx.save();
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.beginPath();
      // Expand each corner outward by pad
      const padded = expandQuad(projected, pad);
      ctx.moveTo(padded[0][0], padded[0][1]);
      for (let i = 1; i < 4; i++) ctx.lineTo(padded[i][0], padded[i][1]);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      // ── Draw image using vertical strip rendering (perspective approximation) ──
      const STRIPS = 32;
      for (let i = 0; i < STRIPS; i++) {
        const t0 = i / STRIPS;
        const t1 = (i + 1) / STRIPS;

        // Interpolate projected corners for this strip
        const topL = lerpPt(projected[0], projected[1], t0);
        const topR = lerpPt(projected[0], projected[1], t1);
        const botL = lerpPt(projected[3], projected[2], t0);
        const botR = lerpPt(projected[3], projected[2], t1);

        // Source strip in original image coordinates
        const srcT0 = mirror ? (1 - t1) : t0;
        const srcT1 = mirror ? (1 - t0) : t1;
        const srcX = srcT0 * imgNatW;
        const srcW = (srcT1 - srcT0) * imgNatW;

        // Affine transform: maps strip-local coords to canvas coords
        // (0,0) → topL, (stripW, 0) → topR, (0, srcH) → botL
        const stripW = Math.abs(srcW);
        if (stripW < 0.01) continue;

        const a = (topR[0] - topL[0]) / stripW;
        const b = (topR[1] - topL[1]) / stripW;
        const c = (botL[0] - topL[0]) / imgNatH;
        const d = (botL[1] - topL[1]) / imgNatH;
        const e = topL[0];
        const f = topL[1];

        ctx.save();
        // Clip to the strip quad
        ctx.beginPath();
        ctx.moveTo(topL[0], topL[1]);
        ctx.lineTo(topR[0], topR[1]);
        ctx.lineTo(botR[0], botR[1]);
        ctx.lineTo(botL[0], botL[1]);
        ctx.closePath();
        ctx.clip();

        // Apply affine transform (concatenates with existing DPR transform)
        ctx.transform(a, b, c, d, e, f);
        ctx.drawImage(img, srcX, 0, Math.abs(srcW), imgNatH, 0, 0, stripW, imgNatH);
        ctx.restore();
      }

      // ── Draw white border on projected quad ──
      ctx.save();
      ctx.strokeStyle = 'rgba(255,255,255,0.3)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(projected[0][0], projected[0][1]);
      for (let i = 1; i < 4; i++) ctx.lineTo(projected[i][0], projected[i][1]);
      ctx.closePath();
      ctx.stroke();
      ctx.restore();
    }

    /** Expand a projected quad outward by pad pixels */
    function expandQuad(pts: [number, number][], pad: number): [number, number][] {
      // Compute centroid
      const cx = (pts[0][0] + pts[1][0] + pts[2][0] + pts[3][0]) / 4;
      const cy = (pts[0][1] + pts[1][1] + pts[2][1] + pts[3][1]) / 4;
      return pts.map(([px, py]) => {
        const dx = px - cx;
        const dy = py - cy;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        return [px + dx / len * pad, py + dy / len * pad] as [number, number];
      });
    }
  }, [width, height, azimuth, elevation, distance, s, rcx, rcy, ringRx, ringRy, elevRx, elevRy, azToRender, azHandlePos, distHandlePos, elevHandlePos]);

  useEffect(() => {
    draw();
  }, [draw]);

  /* ── Hit test ── */
  const hitTest = useCallback((x: number, y: number): DragTarget => {
    const thr = HIT_RADIUS * s;
    const [ax, ay] = azHandlePos(azimuth);
    if (Math.hypot(x - ax, y - ay) <= thr) return 'azimuth';
    const [dx, dy] = distHandlePos(azimuth, distance);
    if (Math.hypot(x - dx, y - dy) <= thr) return 'distance';
    const [ex, ey] = elevHandlePos(elevation);
    if (Math.hypot(x - ex, y - ey) <= thr) return 'elevation';
    return null;
  }, [s, azimuth, elevation, distance, azHandlePos, distHandlePos, elevHandlePos]);

  /* ── Drag update ── */
  const updateFromDrag = useCallback((x: number, y: number, target: DragTarget) => {
    if (!target) return;
    let newAz = azimuth;
    let newEl = elevation;
    let newDist = distance;

    if (target === 'azimuth') {
      const nx = (x - rcx) / ringRx;
      const ny = (y - rcy) / ringRy;
      const renderDeg = Math.atan2(ny, nx) * 180 / Math.PI;
      let display = 90 + AZ_RENDER_OFFSET - renderDeg;
      if (display > 180) display -= 360;
      else if (display < -180) display += 360;
      newAz = Math.round(display);
    } else if (target === 'distance') {
      const a = azToRender(azimuth);
      const cosA = Math.cos(a);
      const sinA = Math.sin(a);
      const lx1 = rcx + DIST_SCALE_MIN * ringRx * cosA;
      const ly1 = rcy + DIST_SCALE_MIN * ringRy * sinA;
      const lx2 = rcx + DIST_SCALE_MAX * ringRx * cosA;
      const ly2 = rcy + DIST_SCALE_MAX * ringRy * sinA;
      const ddx = lx2 - lx1;
      const ddy = ly2 - ly1;
      const lsq = ddx * ddx + ddy * ddy;
      let t = lsq > 0 ? ((x - lx1) * ddx + (y - ly1) * ddy) / lsq : 0;
      t = Math.max(0, Math.min(1, t));
      newDist = Math.round(t * 100) / 10;
    } else if (target === 'elevation') {
      const arcCx = rcx + ELEV_ARC_CX_OFF * s;
      const arcCy = rcy - 20 * s;
      const nx = -(x - arcCx) / elevRx;
      const ny = -(y - arcCy) / elevRy;
      const theta = Math.atan2(ny, nx) * 180 / Math.PI;
      newEl = Math.round(Math.max(-30, Math.min(60, theta - ELEV_RENDER_OFFSET)));
    }

    onChange(newAz, newEl, newDist);
  }, [azimuth, elevation, distance, rcx, rcy, ringRx, ringRy, elevRx, elevRy, s, azToRender, onChange]);

  /* ── Mouse/Touch handlers ── */
  const getPos = (e: React.MouseEvent | React.TouchEvent): [number, number] => {
    const rect = canvasRef.current!.getBoundingClientRect();
    if ('touches' in e) {
      const t = e.touches[0];
      return [t.clientX - rect.left, t.clientY - rect.top];
    }
    return [e.clientX - rect.left, e.clientY - rect.top];
  };

  const handlePointerDown = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.stopPropagation();
    const [x, y] = getPos(e);
    const target = hitTest(x, y);
    if (target) {
      dragRef.current = target;
    }
  }, [hitTest]);

  const handlePointerMove = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (!dragRef.current) return;
    e.stopPropagation();
    e.preventDefault();
    const [x, y] = getPos(e);
    updateFromDrag(x, y, dragRef.current);
  }, [updateFromDrag]);

  const handlePointerUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="nopan nodrag nowheel"
      style={{
        width,
        height,
        cursor: dragRef.current ? 'grabbing' : 'grab',
        touchAction: 'none',
      }}
      onMouseDown={handlePointerDown}
      onMouseMove={handlePointerMove}
      onMouseUp={handlePointerUp}
      onMouseLeave={handlePointerUp}
      onTouchStart={handlePointerDown}
      onTouchMove={handlePointerMove}
      onTouchEnd={handlePointerUp}
    />
  );
}

export const ViewAngleCanvas = memo(ViewAngleCanvasComponent);
