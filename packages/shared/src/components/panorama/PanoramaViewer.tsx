'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

interface PanoramaViewerProps {
  panoramaUrl: string;
  isOpen: boolean;
  onClose: () => void;
  onScreenshot?: (base64: string) => void;
}

export function PanoramaViewer({ panoramaUrl, isOpen, onClose, onScreenshot }: PanoramaViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const animationIdRef = useRef<number>(0);
  const [loading, setLoading] = useState(true);

  // Initialize Three.js scene
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;

    const container = containerRef.current;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 0, 0.1);
    cameraRef.current = camera;

    // Renderer — preserveDrawingBuffer needed for toDataURL
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Inverted sphere for equirectangular panorama
    const geometry = new THREE.SphereGeometry(500, 60, 40);
    geometry.scale(-1, 1, 1);
    const material = new THREE.MeshBasicMaterial({ color: 0x111111 });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    // Load panorama texture
    setLoading(true);
    const loader = new THREE.TextureLoader();
    loader.load(
      panoramaUrl,
      (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        material.map = texture;
        material.color.setHex(0xffffff);
        material.needsUpdate = true;
        setLoading(false);
      },
      undefined,
      () => {
        // If URL load fails, try as base64 data URL
        if (!panoramaUrl.startsWith('data:')) {
          const img = new Image();
          img.crossOrigin = 'anonymous';
          img.onload = () => {
            const tex = new THREE.Texture(img);
            tex.colorSpace = THREE.SRGBColorSpace;
            tex.minFilter = THREE.LinearFilter;
            tex.magFilter = THREE.LinearFilter;
            tex.needsUpdate = true;
            material.map = tex;
            material.color.setHex(0xffffff);
            material.needsUpdate = true;
            setLoading(false);
          };
          img.onerror = () => setLoading(false);
          img.src = panoramaUrl;
        } else {
          setLoading(false);
        }
      },
    );

    // Orbit controls — disable built-in zoom (distance-based) and use FOV zoom instead
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableZoom = false;
    controls.enablePan = false;
    controls.rotateSpeed = -0.5;
    controlsRef.current = controls;

    // FOV-based zoom via mouse wheel
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      camera.fov = Math.max(20, Math.min(100, camera.fov + e.deltaY * 0.05));
      camera.updateProjectionMatrix();
    };
    container.addEventListener('wheel', handleWheel, { passive: false });

    // Animation loop
    const animate = () => {
      animationIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      container.removeEventListener('wheel', handleWheel);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationIdRef.current);
      controls.dispose();
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      if (material.map) material.map.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
    };
  }, [isOpen, panoramaUrl]);

  // Screenshot: render at 1920x1080, capture, restore
  const handleScreenshot = useCallback(() => {
    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const container = containerRef.current;
    if (!renderer || !scene || !camera || !container) return;

    const origW = container.clientWidth;
    const origH = container.clientHeight;

    // Temporarily resize to screenshot dimensions
    const shotW = 1920;
    const shotH = 1080;
    renderer.setSize(shotW, shotH);
    camera.aspect = shotW / shotH;
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);

    const dataUrl = renderer.domElement.toDataURL('image/jpeg', 0.95);

    // Restore
    renderer.setSize(origW, origH);
    camera.aspect = origW / origH;
    camera.updateProjectionMatrix();

    // Extract base64 without prefix
    const base64 = dataUrl.split(',')[1] || dataUrl;
    onScreenshot?.(base64);
  }, [onScreenshot]);

  // Reset view
  const handleRecenter = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(0, 0, 0.1);
    cameraRef.current.fov = 75;
    cameraRef.current.updateProjectionMatrix();
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  }, []);

  if (!isOpen) return null;

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#000',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Three.js container */}
      <div ref={containerRef} style={{ flex: 1, cursor: 'grab' }} />

      {/* Loading overlay */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.8)', zIndex: 10,
        }}>
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
            <div style={{ fontSize: 24, marginBottom: 8, animation: 'spin 1s linear infinite' }}>&#9696;</div>
            <div style={{ fontSize: 13 }}>Loading panorama...</div>
          </div>
        </div>
      )}

      {/* Controls overlay */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 8, zIndex: 20,
      }}>
        {onScreenshot && (
          <button
            onClick={handleScreenshot}
            style={{
              padding: '10px 20px', borderRadius: 12,
              background: 'rgba(59,130,246,0.8)', border: 'none',
              color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              backdropFilter: 'blur(8px)',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(59,130,246,1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(59,130,246,0.8)'; }}
          >
            截图
          </button>
        )}
        <button
          onClick={handleRecenter}
          style={{
            padding: '10px 20px', borderRadius: 12,
            background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
            color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer',
            backdropFilter: 'blur(8px)',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.2)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}
        >
          重置视角
        </button>
        <button
          onClick={onClose}
          style={{
            padding: '10px 20px', borderRadius: 12,
            background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
            color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer',
            backdropFilter: 'blur(8px)',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.2)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}
        >
          关闭
        </button>
      </div>

      {/* ESC hint */}
      <div style={{
        position: 'absolute', top: 16, right: 16, zIndex: 20,
        fontSize: 11, color: 'rgba(255,255,255,0.3)',
      }}>
        ESC 关闭 | 拖拽旋转 | 滚轮缩放
      </div>
    </div>,
    document.body,
  );
}
