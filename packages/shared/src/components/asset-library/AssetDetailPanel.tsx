'use client';

import { useState, useCallback, useEffect, lazy, Suspense } from 'react';
import { createPortal } from 'react-dom';
import { useProjectStore } from '../../stores/projectStore';
import { fetchAPI, API_BASE_URL } from '../../lib/api';
import type { Character, Scene, Location, Prop, CharacterVariant } from '../../types/project';

const PanoramaViewer = lazy(() =>
  import('../panorama/PanoramaViewer').then((m) => ({ default: m.PanoramaViewer })),
);

/* ─── Helper: persist asset image mapping to backend ────── */

function saveAssetImageMapping(
  projectId: string | undefined,
  assetId: string,
  assetType: string,
  slotKey: string,
  storageKey: string,
) {
  if (!projectId || !storageKey) return;
  fetchAPI(`/api/projects/${projectId}/asset-images`, {
    method: 'POST',
    body: JSON.stringify({
      asset_id: assetId,
      asset_type: assetType,
      slot_key: slotKey,
      storage_key: storageKey,
    }),
  }).catch((err: unknown) => console.warn('Failed to save asset image mapping:', err));
}

/* ─── Slot configs per asset type ──────────────────────────── */

const CHARACTER_SLOTS = [
  { key: 'front_full', label: '正前全身' },
  { key: 'left_full', label: '左侧全身', rhPrompt: '<sks> left side view eye-level shot medium shot' },
  { key: 'right_full', label: '右侧全身', rhPrompt: '<sks> right side view eye-level shot medium shot' },
  { key: 'back_full', label: '背影全身', rhPrompt: '<sks> back view eye-level shot medium shot' },
  { key: 'front_half', label: '正前半身', rhPrompt: '<sks> front view eye-level shot close-up' },
];

const LOCATION_SLOTS = [
  { key: 'main', label: '主图' },
];

const PROP_SLOTS = [
  { key: 'front', label: '正面' },
  { key: 'left', label: '左侧', rhPrompt: '<sks> left side view product shot' },
  { key: 'back', label: '背面', rhPrompt: '<sks> back view product shot' },
  { key: 'right', label: '右侧', rhPrompt: '<sks> right side view product shot' },
];

/* ─── Style prompt map ───────────────────────────────────── */

const STYLE_PROMPTS: Record<string, string> = {
  realistic: 'photorealistic, hyperrealistic, DSLR photo, RAW, 8K UHD, natural lighting, cinematic color grading, film grain, shallow depth of field',
  '3d_chinese': 'Chinese 3D animated film style, CG render like Ne Zha or White Snake, stylized character design, vibrant colors, subsurface scattering skin, dramatic volumetric lighting, flowing silk textures, ornate details',
  '2d_chinese': 'Chinese 2D anime style, donghua illustration, cel-shaded, ink wash accents, delicate linework, soft watercolor palette, traditional Chinese aesthetic, elegant hand-drawn feel',
};

/* ─── Image Slot Grid ────────────────────────────────────── */

function ImageSlotGrid({
  assetId,
  slots,
  assetImages,
  prompt,
  aspectRatio,
  onImageGenerated,
  storageKeys,
}: {
  assetId: string;
  slots: { key: string; label: string; rhPrompt?: string }[];
  assetImages: Record<string, string> | undefined;
  prompt: string;
  aspectRatio: string;
  onImageGenerated: (slotKey: string, base64: string, storageKey?: string) => void;
  storageKeys?: Record<string, string>;
}) {
  const loadingSlots = useProjectStore((s) => s.assetLoadingSlots[assetId]) || new Set<string>();
  const errorSlots = useProjectStore((s) => s.assetErrorSlots[assetId]) || new Set<string>();
  const addLoading = useProjectStore((s) => s.addAssetLoadingSlot);
  const removeLoading = useProjectStore((s) => s.removeAssetLoadingSlot);
  const addError = useProjectStore((s) => s.addAssetErrorSlot);
  const removeError = useProjectStore((s) => s.removeAssetErrorSlot);
  const [editingSlot, setEditingSlot] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [previewImg, setPreviewImg] = useState<string | null>(null);
  const [userPrompt, setUserPrompt] = useState(prompt);
  const stylePreset = useProjectStore((s) => s.stylePreset);

  // Sync when external prompt changes (e.g. switching asset)
  useEffect(() => { setUserPrompt(prompt); }, [prompt]);

  const hasAnyLoading = loadingSlots.size > 0;

  // Generate a single RunningHub slot
  const generateRHSlot = useCallback(async (slotKey: string, rhPrompt: string, frontFullKey: string) => {
    addLoading(assetId, slotKey);
    removeError(assetId, slotKey);
    try {
      const result = await fetchAPI<{ image_base64: string; storage_key?: string }>('/api/ai/view-angle-convert', {
        method: 'POST',
        body: JSON.stringify({
          source_storage_key: frontFullKey,
          prompt: rhPrompt,
        }),
      });
      onImageGenerated(slotKey, result.image_base64, result.storage_key ?? undefined);
    } catch (err) {
      console.error(`RunningHub view-angle conversion failed for ${slotKey}:`, err);
      addError(assetId, slotKey);
      setTimeout(() => removeError(assetId, slotKey), 3000);
    } finally {
      removeLoading(assetId, slotKey);
    }
  }, [assetId, addLoading, removeLoading, addError, removeError, onImageGenerated]);

  // Build the final Gemini prompt (shared between fresh gen and refinement)
  const buildGeminiPrompt = useCallback(() => {
    const bgKeywords = /站在|坐在|立于|位于|身处|背景|廊下|门前|窗前|院中|屋内|室内|室外|桥上|树下|花间|月下|雪中|雨中|光影|烛光|月色|阳光|灯光|晨光|夕照|氛围|整体.*氛围|光线|环境|场景/;
    const cleaned = userPrompt
      .split(/[，,。；;]/)
      .filter(seg => !bgKeywords.test(seg.trim()))
      .join('，')
      .trim();
    const basePrompt = cleaned || userPrompt;
    const styleTag = stylePreset ? STYLE_PROMPTS[stylePreset] || '' : '';
    return styleTag ? `${basePrompt}, ${styleTag}` : basePrompt;
  }, [userPrompt, stylePreset]);

  // Gemini generate (fresh, no reference image)
  const generateGeminiFresh = useCallback(async (slotKey: string) => {
    addLoading(assetId, slotKey);
    removeError(assetId, slotKey);
    try {
      const finalPrompt = buildGeminiPrompt();
      const result = await fetchAPI<{ image_base64: string; storage_key?: string }>('/api/ai/generate-image', {
        method: 'POST',
        body: JSON.stringify({ prompt: finalPrompt, aspect_ratio: aspectRatio }),
      });
      onImageGenerated(slotKey, result.image_base64, result.storage_key ?? undefined);
    } catch (err) {
      console.error('Image generation failed:', err);
      addError(assetId, slotKey);
      setTimeout(() => removeError(assetId, slotKey), 3000);
    } finally {
      removeLoading(assetId, slotKey);
    }
  }, [assetId, addLoading, removeLoading, addError, removeError, buildGeminiPrompt, aspectRatio, onImageGenerated]);

  // Gemini refine (with reference image + user description)
  const generateGeminiRefine = useCallback(async (slotKey: string, userDesc: string) => {
    addLoading(assetId, slotKey);
    removeError(assetId, slotKey);
    try {
      const basePrompt = buildGeminiPrompt();
      const refinedPrompt = `${userDesc}, ${basePrompt}`;
      // Get current image as blob for reference
      const imgSrc = assetImages?.[slotKey] || '';
      let blob: Blob | null = null;
      try {
        if (imgSrc.startsWith('http')) {
          // Use no-cors fallback: load via <img> and draw to canvas
          const img = new Image();
          img.crossOrigin = 'anonymous';
          await new Promise<void>((resolve, reject) => {
            img.onload = () => resolve();
            img.onerror = () => reject(new Error('Image load failed'));
            img.src = imgSrc;
          });
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          canvas.getContext('2d')!.drawImage(img, 0, 0);
          blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/png'));
        } else if (imgSrc) {
          const raw = imgSrc.startsWith('data:') ? imgSrc.split(',')[1] : imgSrc;
          const bytes = Uint8Array.from(atob(raw), c => c.charCodeAt(0));
          blob = new Blob([bytes], { type: 'image/png' });
        }
      } catch {
        // If image conversion fails, fall back to fresh generation without reference
        blob = null;
      }

      if (blob) {
        const formData = new FormData();
        formData.append('prompt', refinedPrompt);
        formData.append('aspect_ratio', aspectRatio);
        formData.append('reference', blob, 'reference.png');

        const resp = await fetch(`${API_BASE_URL}/api/ai/generate-image/upload`, {
          method: 'POST',
          body: formData,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const result = await resp.json();
        onImageGenerated(slotKey, result.image_base64, result.storage_key ?? undefined);
      } else {
        // No reference available, do text-only generation with refined prompt
        const result = await fetchAPI<{ image_base64: string; storage_key?: string }>('/api/ai/generate-image', {
          method: 'POST',
          body: JSON.stringify({ prompt: refinedPrompt, aspect_ratio: aspectRatio }),
        });
        onImageGenerated(slotKey, result.image_base64, result.storage_key ?? undefined);
      }
    } catch (err) {
      console.error('Image refinement failed:', err);
      addError(assetId, slotKey);
      setTimeout(() => removeError(assetId, slotKey), 3000);
    } finally {
      removeLoading(assetId, slotKey);
    }
  }, [assetId, addLoading, removeLoading, addError, removeError, buildGeminiPrompt, aspectRatio, assetImages, onImageGenerated]);

  const handleClick = useCallback(async (slotKey: string) => {
    if (hasAnyLoading || !userPrompt.trim()) return;

    // Find slot config
    const slotConfig = slots.find(s => s.key === slotKey);
    const rhPrompt = slotConfig?.rhPrompt;

    // RunningHub path: needs source (first non-RH slot) image first
    if (rhPrompt) {
      const sourceSlot = slots.find(s => !s.rhPrompt);
      const sourceKey = sourceSlot ? storageKeys?.[sourceSlot.key] : undefined;
      if (!sourceKey) {
        alert(`请先生成${sourceSlot?.label || '源'}图`);
        return;
      }
      await generateRHSlot(slotKey, rhPrompt, sourceKey);
      return;
    }

    // Gemini path
    const existingImg = assetImages?.[slotKey];
    if (existingImg) {
      // Has image → show edit input for refinement
      setEditingSlot(slotKey);
      setEditText('');
      return;
    }
    // No image → fresh generate
    await generateGeminiFresh(slotKey);
  }, [hasAnyLoading, prompt, slots, storageKeys, assetImages, generateRHSlot, generateGeminiFresh]);

  // Handle edit input submit
  const handleEditSubmit = useCallback(async () => {
    if (!editingSlot || hasAnyLoading) return;
    const text = editText.trim();
    setEditingSlot(null);
    if (text) {
      // With description → refine based on existing image
      await generateGeminiRefine(editingSlot, text);
    } else {
      // Empty → fresh regenerate without reference
      await generateGeminiFresh(editingSlot);
    }
  }, [editingSlot, editText, hasAnyLoading, generateGeminiRefine, generateGeminiFresh]);

  // Batch generate all RunningHub slots in parallel
  const handleBatchRH = useCallback(async () => {
    if (hasAnyLoading) return;
    const sourceSlot = slots.find(s => !s.rhPrompt);
    const sourceKey = sourceSlot ? storageKeys?.[sourceSlot.key] : undefined;
    if (!sourceKey) {
      alert(`请先生成${sourceSlot?.label || '源'}图`);
      return;
    }
    const rhSlots = slots.filter(s => s.rhPrompt);
    if (rhSlots.length === 0) return;
    // Fire all in parallel — each manages its own loading state
    await Promise.allSettled(
      rhSlots.map(s => generateRHSlot(s.key, s.rhPrompt!, sourceKey))
    );
  }, [hasAnyLoading, storageKeys, slots, generateRHSlot]);

  // Check if there are RunningHub slots and source (first non-RH) is ready
  const rhSlots = slots.filter(s => s.rhPrompt);
  const sourceSlotKey = slots.find(s => !s.rhPrompt)?.key;
  const hasSourceImage = !!(sourceSlotKey && storageKeys?.[sourceSlotKey]);

  // Convert aspect ratio "9:16" to CSS "9 / 16"
  const cssAspect = aspectRatio.replace(':', ' / ');

  return (
    <>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      {/* Editable prompt + generate button */}
      <div className="mb-3 flex gap-2">
        <textarea
          value={userPrompt}
          onChange={(e) => setUserPrompt(e.target.value)}
          rows={3}
          className="flex-1 resize-none rounded-lg border border-white/[0.10] bg-white/[0.03] px-3 py-2 text-xs text-white/80 leading-relaxed outline-none placeholder:text-white/20 focus:border-brand/40 focus:ring-1 focus:ring-brand/20 scrollbar-thin"
          placeholder="输入图片生成提示词..."
        />
        <button
          type="button"
          disabled={hasAnyLoading || !userPrompt.trim()}
          onClick={() => {
            const firstSlot = slots.find(s => !s.rhPrompt);
            if (firstSlot) generateGeminiFresh(firstSlot.key);
          }}
          className={`shrink-0 self-end rounded-lg px-4 py-2 text-xs font-medium transition-all ${
            hasAnyLoading || !userPrompt.trim()
              ? 'cursor-not-allowed bg-white/[0.04] text-white/20'
              : 'bg-brand/20 text-brand hover:bg-brand/30'
          }`}
        >
          {hasAnyLoading ? '生成中...' : '生成'}
        </button>
      </div>
      {/* Batch generate button for RunningHub slots */}
      {rhSlots.length > 0 && hasSourceImage && (
        <button
          type="button"
          onClick={handleBatchRH}
          disabled={hasAnyLoading}
          className={`mb-2 w-full rounded-lg border px-3 py-2 text-xs font-medium transition-all ${
            hasAnyLoading
              ? 'cursor-not-allowed border-white/[0.06] bg-white/[0.02] text-white/20'
              : 'border-brand/30 bg-brand/[0.06] text-brand hover:bg-brand/[0.12]'
          }`}
        >
          {hasAnyLoading ? '生成中...' : '一键生成全部视角'}
        </button>
      )}
      <div className="mb-4" style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(slots.length, 5)}, 1fr)`, gap: '6px' }}>
        {slots.map((slot) => {
        const img = assetImages?.[slot.key];
        const isLoading = loadingSlots.has(slot.key);
        const isError = errorSlots.has(slot.key);
        const isEditing = editingSlot === slot.key;
        const imgSrc = img ? (img.startsWith('data:') || img.startsWith('http') ? img : `data:image/png;base64,${img}`) : '';
        return (
          <div key={slot.key} style={{ position: 'relative' }} className="group">
            {/* Image area — click to preview */}
            <div
              onClick={() => {
                if (isLoading || isError || hasAnyLoading || editingSlot) return;
                if (!img) { handleClick(slot.key); return; }
                setPreviewImg(imgSrc);
              }}
              className={`relative flex w-full items-center justify-center overflow-hidden rounded-lg border transition-all cursor-pointer ${
                isEditing
                  ? 'border-brand/60 ring-1 ring-brand/30'
                  : isLoading
                    ? 'border-brand/40 bg-brand/[0.04]'
                    : isError
                      ? 'border-red-500/40 bg-red-500/[0.04]'
                      : 'border-white/[0.10] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]'
              } ${(hasAnyLoading || editingSlot) && !isLoading && !isEditing ? 'opacity-40 cursor-not-allowed' : ''}`}
              style={{ aspectRatio: cssAspect }}
            >
              {img && !isLoading ? (
                <img src={imgSrc} alt={slot.label} className="h-full w-full object-cover" />
              ) : isLoading ? (
                <div className="flex flex-col items-center gap-2">
                  <div
                    className="h-8 w-8 rounded-full"
                    style={{
                      border: '2px solid rgba(255,255,255,0.1)',
                      borderTopColor: 'var(--color-brand, #6366f1)',
                      animation: 'spin 1s linear infinite',
                    }}
                  />
                  <span className="text-[10px] text-brand/70">生成中...</span>
                </div>
              ) : isError ? (
                <div className="flex flex-col items-center gap-1">
                  <span className="text-sm text-red-400">!</span>
                  <span className="text-[10px] text-red-400/70">生成失败</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-1.5">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-white/15 transition-colors group-hover:text-white/30">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="M21 15l-5-5L5 21" />
                  </svg>
                  <span className="text-[10px] text-white/20 transition-colors group-hover:text-white/40">{slot.label}</span>
                </div>
              )}
            </div>
            {/* Regenerate button — top-right corner text button, visible on hover */}
            {img && !isLoading && !isError && !isEditing && (
              <div
                style={{ position: 'absolute', top: 0, right: 0, zIndex: 20, padding: '4px 4px 8px 8px' }}
                className="opacity-0 transition-opacity group-hover:opacity-100"
              >
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); handleClick(slot.key); }}
                  disabled={hasAnyLoading || !!editingSlot}
                  className="rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-white/90 hover:bg-black/90 transition-colors cursor-pointer"
                >
                  重新生成
                </button>
              </div>
            )}
          </div>
        );
      })}
      </div>
      {/* Refinement input — appears below grid when editing a Gemini slot */}
      {editingSlot && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-brand/30 bg-white/[0.03] px-3 py-2">
          <span className="shrink-0 text-[10px] text-white/40">
            {slots.find(s => s.key === editingSlot)?.label}:
          </span>
          <input
            type="text"
            autoFocus
            value={editText}
            onChange={e => setEditText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleEditSubmit(); if (e.key === 'Escape') setEditingSlot(null); }}
            placeholder="输入调整描述（留空则按原提示词重新生成）"
            className="flex-1 bg-transparent text-xs text-white/80 outline-none placeholder:text-white/20"
          />
          <button
            type="button"
            onClick={handleEditSubmit}
            className="shrink-0 rounded-md bg-brand/20 px-3 py-1 text-[10px] font-medium text-brand hover:bg-brand/30 transition-colors"
          >
            发送
          </button>
          <button
            type="button"
            onClick={() => setEditingSlot(null)}
            className="shrink-0 rounded-md bg-white/[0.06] px-2 py-1 text-[10px] text-white/40 hover:text-white/60 transition-colors"
          >
            取消
          </button>
        </div>
      )}
      {/* Lightbox — rendered via portal to document.body so fixed positioning works */}
      {previewImg && typeof document !== 'undefined' && createPortal(
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 99999, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)', cursor: 'pointer' }}
          onClick={() => setPreviewImg(null)}
        >
          <img
            src={previewImg}
            alt="preview"
            style={{ maxHeight: '90vh', maxWidth: '90vw', borderRadius: 8, objectFit: 'contain', cursor: 'default' }}
            onClick={e => e.stopPropagation()}
          />
        </div>,
        document.body,
      )}
    </>
  );
}

/* ─── Property Row ────────────────────────────────────────── */

function PropRow({ label, value }: { label: string; value: string | undefined }) {
  if (!value) return null;
  return (
    <div className="flex gap-2 py-1.5">
      <span className="shrink-0 text-xs font-medium text-white/30 w-14">{label}</span>
      <span className="text-xs text-white/60 leading-relaxed">{value}</span>
    </div>
  );
}

/* ─── Character Detail ────────────────────────────────────── */

function CharacterDetail({ character }: { character: Character }) {
  const { assetImages, assetImageKeys, setAssetImage, setAssetImageKey, project, characterVariants, removeCharacterVariant } = useProjectStore();
  const images = assetImages[character.id];
  const keys = assetImageKeys[character.id];
  const [activeTab, setActiveTab] = useState<'original' | string>('original');

  // Get variants belonging to this character
  const variants = characterVariants.filter(v => v.character_id === character.id);

  // Reset tab if selected variant no longer exists
  useEffect(() => {
    if (activeTab !== 'original' && !variants.some(v => v.id === activeTab)) {
      setActiveTab('original');
    }
  }, [activeTab, variants]);

  const handleImageGenerated = useCallback((slotKey: string, base64: string, storageKey?: string) => {
    setAssetImage(character.id, slotKey, base64);
    if (storageKey) {
      setAssetImageKey(character.id, slotKey, storageKey);
    }
    saveAssetImageMapping(project?.id, character.id, 'character', slotKey, storageKey ?? '');
  }, [character.id, setAssetImage, setAssetImageKey, project?.id]);

  const ROLE_LABELS: Record<string, string> = {
    protagonist: '主角', antagonist: '反派', supporting: '配角', minor: '龙套',
  };
  const ROLE_COLORS: Record<string, string> = {
    protagonist: 'bg-amber-400/20 text-amber-300',
    antagonist: 'bg-red-400/20 text-red-300',
    supporting: 'bg-sky-400/20 text-sky-300',
    minor: 'bg-white/10 text-white/50',
  };

  let roleBoost = '';
  if (character.role === 'protagonist') {
    roleBoost = 'stunning, gorgeous, attractive, captivating, charming, ';
  } else if (character.role === 'antagonist') {
    const flaw = (character.flaw || character.personality || '').toLowerCase();
    const isCreepy = /阴|狠|毒|邪|诡|冷血|残|恐|鬼/.test(flaw);
    const isScheming = /算计|虚伪|伪善|笑里藏刀|城府|阴险/.test(flaw);
    if (isCreepy) {
      roleBoost = 'intimidating, menacing, unsettling, fearsome, cold piercing eyes, ';
    } else if (isScheming) {
      roleBoost = 'cunning, deceptive smile, scheming eyes, unsettling elegance, ';
    } else {
      roleBoost = 'imposing, intimidating presence, sharp hostile gaze, ';
    }
  }
  const charPromptBase = character.visual_reference || character.personality || character.name;

  // Currently selected variant (if any)
  const selectedVariant = activeTab !== 'original' ? variants.find(v => v.id === activeTab) : null;

  return (
    <div className="p-5 pb-24">
      {/* Character image grid — always visible as anchor */}
      <ImageSlotGrid
        assetId={character.id}
        slots={CHARACTER_SLOTS}
        assetImages={images}
        prompt={`white background, full body front view, arms naturally at sides, empty hands, solo, only one person, no other characters, no other people, single character only, ${roleBoost}${charPromptBase}`}
        aspectRatio="9:16"
        onImageGenerated={handleImageGenerated}
        storageKeys={keys}
      />

      {/* Name + Role badge */}
      <div className="flex items-center gap-2 mb-1">
        <h3 className="text-lg font-bold text-white/95">{character.name}</h3>
        {character.role && (
          <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${ROLE_COLORS[character.role] || ROLE_COLORS.minor}`}>
            {ROLE_LABELS[character.role] || character.role}
          </span>
        )}
      </div>

      {/* Pill Tab bar — only show when variants exist */}
      {variants.length > 0 && (
        <div className="mb-4 mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('original')}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all ring-1 ring-inset ${
              activeTab === 'original'
                ? 'bg-purple-500/20 text-purple-300 ring-purple-500/40'
                : 'bg-white/[0.03] text-white/40 ring-white/[0.10] hover:bg-white/[0.06] hover:text-white/60'
            }`}
          >
            原始
          </button>
          {variants.map(v => (
            <button
              key={v.id}
              type="button"
              onClick={() => setActiveTab(v.id)}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all ring-1 ring-inset ${
                activeTab === v.id
                  ? 'bg-pink-500/20 text-pink-300 ring-pink-500/40'
                  : 'bg-white/[0.03] text-white/40 ring-white/[0.10] hover:bg-white/[0.06] hover:text-white/60'
              }`}
            >
              {v.variant_name || v.variant_type || '变体'}
            </button>
          ))}
          {/* Generate variant button */}
          <button
            type="button"
            onClick={() => {
              if (project?.id) {
                fetchAPI(`/api/projects/${project.id}/assets/regenerate/variant/${character.id}`, { method: 'POST' })
                  .catch(err => console.error('Variant generation failed:', err));
              }
            }}
            className="shrink-0 rounded-full px-3 py-1.5 text-xs text-white/30 ring-1 ring-inset ring-dashed ring-white/[0.10] hover:bg-white/[0.06] hover:text-white/50 transition-all"
            title="生成新变体"
          >
            <svg className="inline h-3 w-3 mr-0.5 -mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
            变体
          </button>
        </div>
      )}

      {/* Tab content: Original */}
      {activeTab === 'original' && (
        <>
          {character.aliases && character.aliases.length > 0 && (
            <p className="text-xs text-white/30 mb-1">别名: {character.aliases.join('、')}</p>
          )}
          {character.description && (
            <p className="text-xs text-white/40 mb-1">{character.description}</p>
          )}
          {character.age_range && (
            <p className="text-xs text-white/30 mb-3">年龄: {character.age_range}</p>
          )}

          {/* Casting tags */}
          {character.casting_tags && character.casting_tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-4">
              {character.casting_tags.map((tag) => (
                <span key={tag} className="rounded-full bg-purple-500/8 px-2 py-0.5 text-[10px] text-purple-300/70 ring-1 ring-inset ring-purple-500/10">
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Core traits: personality, desire, flaw */}
          <div className="divide-y divide-white/[0.04] mb-4">
            <PropRow label="性格" value={character.personality} />
            <PropRow label="欲望" value={character.desire} />
            <PropRow label="缺陷" value={character.flaw} />
          </div>

          {/* Appearance section */}
          {character.appearance && (
            <div className="mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">外貌</p>
              <div className="divide-y divide-white/[0.04]">
                <PropRow label="面部" value={character.appearance.face} />
                <PropRow label="身体" value={character.appearance.body} />
                <PropRow label="发型" value={character.appearance.hair} />
                <PropRow label="特征" value={character.appearance.distinguishing_features} />
              </div>
            </div>
          )}

          {/* Costume section */}
          {character.costume && (
            <div className="mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">服装</p>
              <PropRow label="典型" value={character.costume.typical_outfit} />
              {character.costume.color_palette && character.costume.color_palette.length > 0 && (
                <div className="flex items-center gap-2 py-1.5">
                  <span className="shrink-0 text-xs font-medium text-white/30 w-14">色板</span>
                  <div className="flex flex-wrap gap-1">
                    {character.costume.color_palette.map((c) => (
                      <span key={c} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-white/50 ring-1 ring-inset ring-white/[0.06]">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {character.costume.texture_keywords && character.costume.texture_keywords.length > 0 && (
                <div className="flex items-center gap-2 py-1.5">
                  <span className="shrink-0 text-xs font-medium text-white/30 w-14">材质</span>
                  <div className="flex flex-wrap gap-1">
                    {character.costume.texture_keywords.map((t: string) => (
                      <span key={t} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-white/50 ring-1 ring-inset ring-white/[0.06]">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {character.arc && (
            <div className="mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">人物弧线</p>
              <p className="text-xs text-white/50 leading-relaxed">{character.arc}</p>
            </div>
          )}

          {/* Scene presence */}
          {character.scene_presence && (
            <div className="mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">出场概述</p>
              <p className="text-xs text-white/50 leading-relaxed">{character.scene_presence}</p>
            </div>
          )}

          {/* Relationships */}
          {character.relationships && character.relationships.length > 0 && (
            <div className="mb-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">关系网</p>
              <div className="space-y-2">
                {character.relationships.map((rel, i) => {
                  const targetName = rel.target || rel.target_character_id || '未知';
                  const relType = rel.type || rel.relationship_type || '';
                  const relDesc = rel.dynamic || rel.description || '';
                  const relFunc = rel.function || '';
                  return (
                    <div key={i} className="rounded-lg border border-white/[0.04] bg-white/[0.02] p-2.5">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-white/80">{targetName}</span>
                        {relType && (
                          <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[9px] text-purple-300/70">
                            {relType}
                          </span>
                        )}
                      </div>
                      {relDesc && <p className="text-[11px] text-white/40 leading-relaxed">{relDesc}</p>}
                      {relFunc && <p className="mt-1 text-[10px] text-white/25 italic">{relFunc}</p>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Visual reference */}
          <div className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/25">Visual Reference</p>
            <p className="text-xs text-white/50 leading-relaxed">
              {character.visual_reference || '暂无视觉参考描述'}
            </p>
          </div>

          {/* Negative prompt */}
          {character.visual_prompt_negative && (
            <div className="mt-3 rounded-lg border border-white/[0.04] bg-white/[0.01] p-3">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/20">Negative Prompt</p>
              <p className="text-[11px] text-white/30 leading-relaxed">{character.visual_prompt_negative}</p>
            </div>
          )}
        </>
      )}

      {/* Tab content: Variant */}
      {selectedVariant && (
        <CharacterVariantTab variant={selectedVariant} onDelete={() => {
          if (project?.id) {
            fetchAPI(`/api/projects/${project.id}/variants/${selectedVariant.id}`, { method: 'DELETE' })
              .then(() => removeCharacterVariant(selectedVariant.id))
              .catch(err => console.error('Delete variant failed:', err));
          }
          setActiveTab('original');
        }} />
      )}
    </div>
  );
}

/* ─── Character Variant Tab (inline in CharacterDetail) ──── */

function CharacterVariantTab({ variant, onDelete }: { variant: CharacterVariant; onDelete: () => void }) {
  const { assetImages, assetImageKeys, setAssetImage, setAssetImageKey, project } = useProjectStore();

  const images = assetImages[variant.id];
  const keys = assetImageKeys[variant.id];

  const handleImageGenerated = useCallback((slotKey: string, base64: string, storageKey?: string) => {
    setAssetImage(variant.id, slotKey, base64);
    if (storageKey) {
      setAssetImageKey(variant.id, slotKey, storageKey);
    }
    saveAssetImageMapping(project?.id, variant.id, 'variant', slotKey, storageKey ?? '');
  }, [variant.id, setAssetImage, setAssetImageKey, project?.id]);

  return (
    <>
      {/* Variant image grid */}
      <ImageSlotGrid
        assetId={variant.id}
        slots={CHARACTER_SLOTS}
        assetImages={images}
        prompt={`white background, full body front view, arms naturally at sides, empty hands, solo, only one person, no other characters, no other people, single character only, ${variant.visual_reference || variant.variant_name || variant.character_name}`}
        aspectRatio="9:16"
        onImageGenerated={handleImageGenerated}
        storageKeys={keys}
      />

      {/* Variant info */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-white/50">{variant.variant_name}</span>
        {variant.variant_type && (
          <span className="rounded-md bg-pink-500/10 px-1.5 py-0.5 text-[10px] font-medium text-pink-300/80 ring-1 ring-inset ring-pink-500/10">
            {variant.variant_type}
          </span>
        )}
      </div>

      {variant.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {variant.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-pink-500/10 px-2 py-0.5 text-[10px] text-pink-300/70 ring-1 ring-inset ring-pink-500/15">
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="divide-y divide-white/[0.04] mb-4">
        <PropRow label="触发" value={variant.trigger} />
        <PropRow label="情绪" value={variant.emotional_tone} />
      </div>

      {variant.appearance_delta && Object.keys(variant.appearance_delta).length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">外观变化</p>
          <div className="divide-y divide-white/[0.04]">
            {Object.entries(variant.appearance_delta).map(([key, val]) => (
              <PropRow key={key} label={key} value={String(val)} />
            ))}
          </div>
        </div>
      )}

      {variant.costume_override && Object.keys(variant.costume_override).length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">服装覆盖</p>
          <div className="divide-y divide-white/[0.04]">
            {Object.entries(variant.costume_override).map(([key, val]) => (
              <PropRow key={key} label={key} value={String(val)} />
            ))}
          </div>
        </div>
      )}

      {variant.scene_ids && variant.scene_ids.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">关联场景</p>
          <div className="flex flex-wrap gap-1">
            {variant.scene_ids.map((s: string) => (
              <span key={s} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-white/40 ring-1 ring-inset ring-white/[0.06]">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/25">Visual Reference</p>
        <p className="text-xs text-white/50 leading-relaxed line-clamp-4">
          {variant.visual_reference || '暂无视觉参考描述'}
        </p>
      </div>

      {variant.visual_prompt_negative && (
        <div className="mt-3 rounded-lg border border-white/[0.04] bg-white/[0.01] p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/20">Negative Prompt</p>
          <p className="text-[11px] text-white/30 leading-relaxed">{variant.visual_prompt_negative}</p>
        </div>
      )}

      {/* Delete variant button */}
      <button
        type="button"
        onClick={onDelete}
        className="mt-4 w-full rounded-lg border border-red-500/20 bg-red-500/[0.06] px-3 py-2 text-xs font-medium text-red-300/80 hover:bg-red-500/[0.12] transition-colors"
      >
        删除此变体
      </button>
    </>
  );
}

/* ─── Location Detail ─────────────────────────────────────── */

function LocationDetail({ location }: { location: Location }) {
  const { assetImages, assetImageKeys, setAssetImage, setAssetImageKey, screenFormat, project } = useProjectStore();
  const [panoramaLoading, setPanoramaLoading] = useState(false);
  const [panoramaViewerOpen, setPanoramaViewerOpen] = useState(false);

  const images = assetImages[location.id];
  const keys = assetImageKeys[location.id];

  // Backward compat: read 'main' or fallback to 'east'
  const mainImage = images?.['main'] || images?.['east'];
  const mainKey = keys?.['main'] || keys?.['east'];
  const panoramaImage = images?.['panorama'];

  // Provide compatible images record for ImageSlotGrid
  const compatImages = images ? { ...images, main: mainImage || '' } : undefined;
  const compatKeys = keys ? { ...keys, main: mainKey || '' } : undefined;

  const handleImageGenerated = useCallback((slotKey: string, base64: string, storageKey?: string) => {
    setAssetImage(location.id, slotKey, base64);
    if (storageKey) {
      setAssetImageKey(location.id, slotKey, storageKey);
    }
    saveAssetImageMapping(project?.id, location.id, 'location', slotKey, storageKey ?? '');
  }, [location.id, setAssetImage, setAssetImageKey, project?.id]);

  // Generate 360° panorama from main image
  const handleGeneratePanorama = useCallback(async () => {
    if (!mainKey || panoramaLoading) return;
    setPanoramaLoading(true);
    try {
      const result = await fetchAPI<{ image_base64: string; storage_key?: string }>(
        '/api/ai/generate-panorama',
        {
          method: 'POST',
          body: JSON.stringify({
            reference_storage_key: mainKey,
            prompt: `no people, no person, no human, empty scene environment only. ${location.visual_reference || location.visual_description || location.name}`,
          }),
        },
      );
      handleImageGenerated('panorama', result.image_base64, result.storage_key ?? undefined);
    } catch (err) {
      console.error('Panorama generation failed:', err);
      alert('全景图生成失败，请重试');
    } finally {
      setPanoramaLoading(false);
    }
  }, [mainKey, panoramaLoading, location, handleImageGenerated]);

  // Handle panorama screenshot
  const handlePanoramaScreenshot = useCallback(async (base64: string) => {
    // Store as panorama_screenshot slot
    handleImageGenerated('panorama_screenshot', base64);
    // Upload to backend storage
    try {
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: 'image/jpeg' });
      const formData = new FormData();
      formData.append('file', blob, 'panorama_screenshot.jpg');
      const resp = await fetch(
        `${API_BASE_URL}/api/projects/${project?.id}/asset-images/upload`,
        { method: 'POST', body: formData },
      );
      if (resp.ok) {
        const data = await resp.json();
        if (data.storage_key) {
          setAssetImageKey(location.id, 'panorama_screenshot', data.storage_key);
          saveAssetImageMapping(project?.id, location.id, 'location', 'panorama_screenshot', data.storage_key);
        }
      }
    } catch (err) {
      console.warn('Failed to upload panorama screenshot:', err);
    }
  }, [handleImageGenerated, project?.id, location.id, setAssetImageKey]);

  // Build panorama URL for viewer
  const panoramaUrl = panoramaImage
    ? panoramaImage.startsWith('data:') || panoramaImage.startsWith('http')
      ? panoramaImage
      : `data:image/png;base64,${panoramaImage}`
    : '';

  return (
    <div className="p-5 pb-24">
      <ImageSlotGrid
        assetId={location.id}
        slots={LOCATION_SLOTS}
        assetImages={compatImages}
        prompt={`no people, no person, no human, empty scene, ${location.visual_reference || location.visual_description || location.name}`}
        aspectRatio={screenFormat === 'vertical' ? '9:16' : '16:9'}
        onImageGenerated={handleImageGenerated}
        storageKeys={compatKeys}
      />

      {/* 360° Panorama section */}
      <div className="mt-4 mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">360° VR 全景</p>

        {panoramaImage ? (
          <div className="relative group">
            <img
              src={panoramaUrl}
              alt="360° panorama"
              crossOrigin="anonymous"
              className="w-full rounded-xl border border-white/[0.06] cursor-pointer"
              style={{ aspectRatio: '2/1', objectFit: 'cover' }}
              onClick={() => setPanoramaViewerOpen(true)}
            />
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40 rounded-xl">
              <span className="text-white text-sm font-medium">查看 360°</span>
            </div>
          </div>
        ) : (
          <button
            onClick={handleGeneratePanorama}
            disabled={!mainKey || panoramaLoading}
            className="w-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] py-6 text-center transition-colors hover:bg-white/[0.04] hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {panoramaLoading ? (
              <span className="text-[12px] text-white/40">生成全景图中...</span>
            ) : !mainKey ? (
              <span className="text-[12px] text-white/30">请先生成主图</span>
            ) : (
              <span className="text-[12px] text-white/50">生成 360° 全景图</span>
            )}
          </button>
        )}

        {panoramaImage && (
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => setPanoramaViewerOpen(true)}
              className="flex-1 rounded-lg bg-blue-500/15 px-3 py-1.5 text-[11px] font-medium text-blue-300/80 hover:bg-blue-500/25 transition-colors"
            >
              查看 360°
            </button>
            <button
              onClick={handleGeneratePanorama}
              disabled={panoramaLoading}
              className="rounded-lg bg-white/[0.04] px-3 py-1.5 text-[11px] text-white/40 hover:bg-white/[0.08] transition-colors disabled:opacity-30"
            >
              {panoramaLoading ? '生成中...' : '重新生成'}
            </button>
          </div>
        )}
      </div>

      {/* Panorama Viewer modal */}
      {panoramaViewerOpen && panoramaUrl && (
        <Suspense fallback={null}>
          <PanoramaViewer
            isOpen={panoramaViewerOpen}
            panoramaUrl={panoramaUrl}
            onClose={() => setPanoramaViewerOpen(false)}
            onScreenshot={handlePanoramaScreenshot}
          />
        </Suspense>
      )}

      <h3 className="text-lg font-bold text-white/95 mb-1">{location.name}</h3>

      {/* Type & Era */}
      <div className="mt-1.5 flex flex-wrap gap-1.5 mb-3">
        {location.type && (
          <span className="rounded-md bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-300/80 ring-1 ring-inset ring-green-500/10">
            {location.type}
          </span>
        )}
        {location.era_style && (
          <span className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium text-blue-300/80 ring-1 ring-inset ring-blue-500/10">
            {location.era_style}
          </span>
        )}
      </div>

      <div className="divide-y divide-white/[0.04]">
        <PropRow label="描述" value={location.description} />
        <PropRow label="氛围" value={location.atmosphere || location.mood} />
        <PropRow label="光照" value={location.lighting} />
        <PropRow label="情绪" value={location.emotional_range} />
        <PropRow label="感知" value={location.sensory} />
        <PropRow label="叙事" value={location.narrative_function} />
      </div>

      {/* Color Palette */}
      {location.color_palette && location.color_palette.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">色彩</p>
          <div className="flex flex-wrap gap-1">
            {location.color_palette.map((c) => (
              <span key={c} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-white/50 ring-1 ring-inset ring-white/[0.06]">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Key Features */}
      {location.key_features && location.key_features.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">关键特征</p>
          <div className="flex flex-wrap gap-1">
            {location.key_features.map((f) => (
              <span key={f} className="rounded-full bg-green-500/8 px-2 py-0.5 text-[10px] text-green-300/60 ring-1 ring-inset ring-green-500/10">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Time Variations */}
      {location.time_variations && location.time_variations.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">时段</p>
          <div className="flex flex-wrap gap-1">
            {location.time_variations.map((t) => (
              <span key={t} className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300/70 ring-1 ring-inset ring-amber-500/10">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Scene count */}
      {location.scene_count != null && location.scene_count > 0 && (
        <div className="mt-3 text-[10px] text-white/30">
          出现场景数: {location.scene_count}
        </div>
      )}

      {/* Visual reference */}
      <div className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/25">Visual Reference</p>
        <p className="text-xs text-white/50 leading-relaxed line-clamp-6">
          {location.visual_reference || location.visual_description || '暂无视觉参考描述'}
        </p>
      </div>

      {/* Negative prompt */}
      {location.visual_prompt_negative && (
        <div className="mt-3 rounded-lg border border-white/[0.04] bg-white/[0.01] p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/20">Negative Prompt</p>
          <p className="text-[11px] text-white/30 leading-relaxed">{location.visual_prompt_negative}</p>
        </div>
      )}
    </div>
  );
}

/* ─── Prop Detail ─────────────────────────────────────────── */

function PropDetail({ prop }: { prop: Prop }) {
  const { assetImages, assetImageKeys, setAssetImage, setAssetImageKey, project } = useProjectStore();

  const images = assetImages[prop.id];
  const keys = assetImageKeys[prop.id];

  const handleImageGenerated = useCallback((slotKey: string, base64: string, storageKey?: string) => {
    setAssetImage(prop.id, slotKey, base64);
    if (storageKey) {
      setAssetImageKey(prop.id, slotKey, storageKey);
    }
    saveAssetImageMapping(project?.id, prop.id, 'prop', slotKey, storageKey ?? '');
  }, [prop.id, setAssetImage, setAssetImageKey, project?.id]);

  return (
    <div className="p-5 pb-24">
      <ImageSlotGrid
        assetId={prop.id}
        slots={PROP_SLOTS}
        assetImages={images}
        prompt={`white background, single object only, no other items, no extra objects, product photo, ${prop.visual_reference || prop.description || prop.name}`}
        aspectRatio="1:1"
        onImageGenerated={handleImageGenerated}
        storageKeys={keys}
      />

      <h3 className="text-lg font-bold text-white/95 mb-1">{prop.name}</h3>

      {/* Badges */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {prop.is_major && (
          <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300/80 ring-1 ring-inset ring-amber-500/10">
            主要道具
          </span>
        )}
        {prop.is_motif && (
          <span className="rounded-md bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-medium text-purple-300/80 ring-1 ring-inset ring-purple-500/10">
            母题
          </span>
        )}
        {(prop.appearance_count ?? 0) > 0 && (
          <span className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium text-blue-300/80 ring-1 ring-inset ring-blue-500/10">
            出场 {prop.appearance_count} 次
          </span>
        )}
      </div>

      <div className="divide-y divide-white/[0.04]">
        <PropRow label="分类" value={prop.category} />
        <PropRow label="描述" value={prop.description} />
        <PropRow label="叙事" value={prop.narrative_function} />
        <PropRow label="情感" value={prop.emotional_association} />
      </div>

      {/* Scenes present */}
      {prop.scenes_present && prop.scenes_present.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">出现场景</p>
          <div className="flex flex-wrap gap-1">
            {prop.scenes_present.map((s: string) => (
              <span key={s} className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-white/40 ring-1 ring-inset ring-white/[0.06]">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/25">Visual Reference</p>
        <p className="text-xs text-white/50 leading-relaxed line-clamp-4">
          {prop.visual_reference || '暂无视觉参考描述'}
        </p>
      </div>

      {/* Negative prompt */}
      {prop.visual_prompt_negative && (
        <div className="mt-3 rounded-lg border border-white/[0.04] bg-white/[0.01] p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/20">Negative Prompt</p>
          <p className="text-[11px] text-white/30 leading-relaxed">{prop.visual_prompt_negative}</p>
        </div>
      )}
    </div>
  );
}

/* ─── Scene Detail ────────────────────────────────────────── */

function SceneDetail({ scene, locations }: { scene: Scene; locations: Location[] }) {
  const matchedLocation = locations.find(
    (l) => l.name === scene.location || l.id === scene.location,
  );
  const { assetImages } = useProjectStore();
  const locationImages = matchedLocation ? assetImages[matchedLocation.id] : undefined;

  const durationMin = scene.estimated_duration_s ? Math.round(scene.estimated_duration_s / 60) : null;
  const durationLabel = scene.estimated_duration_s
    ? (durationMin && durationMin > 0 ? `${durationMin}分${scene.estimated_duration_s % 60}秒` : `${scene.estimated_duration_s}秒`)
    : null;

  const TIME_LABELS: Record<string, string> = { day: '白天', night: '夜晚', dawn: '黎明', dusk: '黄昏' };

  return (
    <div className="p-5 pb-24">
      {/* Show location images if available */}
      {locationImages && Object.keys(locationImages).length > 0 && (
        <div className="grid grid-cols-2 gap-3 mb-5">
          {Object.entries(locationImages).slice(0, 4).map(([slot, img]) => (
            <div key={slot} className="aspect-[3/4] overflow-hidden rounded-xl border border-white/[0.06]">
              <img
                src={img.startsWith('data:') || img.startsWith('http') ? img : `data:image/png;base64,${img}`}
                alt={slot}
                className="h-full w-full object-cover"
              />
            </div>
          ))}
        </div>
      )}

      {/* Heading */}
      <h3 className="text-lg font-bold text-white/95 mb-1">
        {scene.heading || scene.location || '场景'}
      </h3>

      {/* Location + Time badges */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {scene.location && (
          <span className="rounded-md bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-300/80 ring-1 ring-inset ring-green-500/10">
            {scene.location}
          </span>
        )}
        {scene.time_of_day && (
          <span className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300/80 ring-1 ring-inset ring-amber-500/10">
            {TIME_LABELS[scene.time_of_day] || scene.time_of_day}
          </span>
        )}
        {durationLabel && (
          <span className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium text-blue-300/80 ring-1 ring-inset ring-blue-500/10">
            {durationLabel}
          </span>
        )}
      </div>

      {/* Core event */}
      {scene.core_event && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">核心事件</p>
          <p className="text-xs text-white/60 leading-relaxed">{scene.core_event}</p>
        </div>
      )}

      {/* Description */}
      {scene.description && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">场景描述</p>
          <p className="text-xs text-white/50 leading-relaxed">{scene.description}</p>
        </div>
      )}

      {/* Action */}
      {scene.action && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">动作</p>
          <p className="text-xs text-white/50 leading-relaxed">{scene.action}</p>
        </div>
      )}

      {/* Key dialogue */}
      {scene.key_dialogue && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">关键对白</p>
          <p className="text-xs text-white/60 leading-relaxed italic">&ldquo;{scene.key_dialogue}&rdquo;</p>
        </div>
      )}

      {/* Emotional peak */}
      {scene.emotional_peak && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">情感高潮</p>
          <p className="text-xs text-white/50 leading-relaxed">{scene.emotional_peak}</p>
        </div>
      )}

      {/* Dramatic purpose */}
      {scene.dramatic_purpose && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">叙事功能</p>
          <p className="text-xs text-white/50 leading-relaxed">{scene.dramatic_purpose}</p>
        </div>
      )}

      {/* Characters present */}
      {scene.characters_present && scene.characters_present.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">出场角色</p>
          <div className="flex flex-wrap gap-1">
            {scene.characters_present.map((c) => (
              <span key={c} className="rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] text-purple-300/70 ring-1 ring-inset ring-purple-500/15">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Key props */}
      {scene.key_props && scene.key_props.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">关键道具</p>
          <div className="flex flex-wrap gap-1">
            {scene.key_props.map((p) => (
              <span key={p} className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] text-sky-300/70 ring-1 ring-inset ring-sky-500/15">
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Dialogue list */}
      {scene.dialogue && scene.dialogue.length > 0 && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-2">对白</p>
          <div className="space-y-1.5">
            {scene.dialogue.map((d, i) => (
              <div key={i} className="rounded-lg border border-white/[0.04] bg-white/[0.02] p-2">
                <span className="text-[10px] font-medium text-purple-300/70">{d.character}</span>
                {d.parenthetical && <span className="ml-1 text-[9px] text-white/25">({d.parenthetical})</span>}
                <p className="mt-0.5 text-[11px] text-white/50 leading-relaxed">{d.line}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tension score */}
      {scene.tension_score != null && (
        <div className="mb-4 flex items-center gap-2">
          <span className="text-[10px] text-white/25">张力</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-blue-400/60 transition-all"
              style={{ width: `${Math.min(scene.tension_score * 100, 100)}%` }}
            />
          </div>
          <span className="text-[10px] text-white/30">{scene.tension_score.toFixed(1)}</span>
        </div>
      )}

      {/* Source text excerpts */}
      {(scene.source_text_start || scene.source_text_end) && (
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">原文摘录</p>
          {scene.source_text_start && (
            <p className="text-[11px] text-white/30 leading-relaxed mb-1">{scene.source_text_start}</p>
          )}
          {scene.source_text_start && scene.source_text_end && (
            <p className="text-[10px] text-white/15 mb-1">...</p>
          )}
          {scene.source_text_end && (
            <p className="text-[11px] text-white/30 leading-relaxed">{scene.source_text_end}</p>
          )}
        </div>
      )}

      {/* Visual reference */}
      {scene.visual_reference && (
        <div className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/25">Visual Reference</p>
          <p className="text-xs text-white/50 leading-relaxed">{scene.visual_reference}</p>
        </div>
      )}

      {/* Negative prompt */}
      {scene.visual_prompt_negative && (
        <div className="mt-3 rounded-lg border border-white/[0.04] bg-white/[0.01] p-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/20">Negative Prompt</p>
          <p className="text-[11px] text-white/30 leading-relaxed">{scene.visual_prompt_negative}</p>
        </div>
      )}
    </div>
  );
}

/* ─── Main Detail Panel ───────────────────────────────────── */

/* ─── Regenerate Button ──────────────────────────────────── */

function RegenerateButton({
  assetType,
  assetId,
  projectId,
}: {
  assetType: 'character' | 'prop' | 'location';
  assetId: string;
  projectId: string | undefined;
}) {
  const [regenerating, setRegenerating] = useState(false);

  if (!projectId) return null;

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/assets/regenerate/${assetType}/${assetId}`, {
        method: 'POST',
      });
      if (!resp.ok) {
        console.error('Regeneration failed');
      }
    } catch (e) {
      console.error('Regeneration request failed:', e);
    } finally {
      // Give the backend some time to process
      setTimeout(() => setRegenerating(false), 5000);
    }
  };

  return (
    <button
      type="button"
      onClick={handleRegenerate}
      disabled={regenerating}
      className={`
        flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors
        ${regenerating
          ? 'cursor-not-allowed bg-white/5 text-white/20'
          : 'bg-brand/10 text-brand hover:bg-brand/20'
        }
      `}
    >
      {regenerating ? (
        <>
          <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40 60" />
          </svg>
          重新生成中...
        </>
      ) : (
        <>
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M1 4v6h6M23 20v-6h-6" />
            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
          </svg>
          重新生成
        </>
      )}
    </button>
  );
}

interface AssetDetailPanelProps {
  characters: Character[];
  scenes: Scene[];
  locations: Location[];
  props: Prop[];
  projectId?: string;
}

export function AssetDetailPanel({
  characters,
  scenes,
  locations,
  props,
  projectId,
}: AssetDetailPanelProps) {
  const { selectedAssetId, selectedAssetType } = useProjectStore();

  if (!selectedAssetId || !selectedAssetType) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-3 text-white/10">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M9 9h6v6H9z" />
          </svg>
          <p className="text-sm text-white/25">选择一个资产查看详情</p>
        </div>
      </div>
    );
  }

  // Find the selected asset
  switch (selectedAssetType) {
    case 'character': {
      const character = characters.find((c) => c.id === selectedAssetId);
      if (!character) return <EmptyState />;
      return (
        <div className="h-full overflow-y-auto scrollbar-thin">
          <div className="flex items-center justify-end px-6 pt-4">
            <RegenerateButton assetType="character" assetId={character.id} projectId={projectId} />
          </div>
          <CharacterDetail character={character} />
        </div>
      );
    }
    case 'scene': {
      const scene = scenes.find((s) => s.id === selectedAssetId);
      if (!scene) return <EmptyState />;
      return (
        <div className="h-full overflow-y-auto scrollbar-thin">
          <SceneDetail scene={scene} locations={locations} />
        </div>
      );
    }
    case 'location': {
      const location = locations.find((l) => l.id === selectedAssetId);
      if (!location) return <EmptyState />;
      return (
        <div className="h-full overflow-y-auto scrollbar-thin">
          <div className="flex items-center justify-end px-6 pt-4">
            <RegenerateButton assetType="location" assetId={location.id} projectId={projectId} />
          </div>
          <LocationDetail location={location} />
        </div>
      );
    }
    case 'prop': {
      const prop = props.find((p) => p.id === selectedAssetId);
      if (!prop) return <EmptyState />;
      return (
        <div className="h-full overflow-y-auto scrollbar-thin">
          <div className="flex items-center justify-end px-6 pt-4">
            <RegenerateButton assetType="prop" assetId={prop.id} projectId={projectId} />
          </div>
          <PropDetail prop={prop} />
        </div>
      );
    }
    default:
      return <EmptyState />;
  }
}

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <p className="text-sm text-white/25">资产未找到</p>
    </div>
  );
}
