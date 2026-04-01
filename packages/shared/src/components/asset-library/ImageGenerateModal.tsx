'use client';

import { useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { fetchAPI } from '../../lib/api';

interface ImageGenerateModalProps {
  open: boolean;
  onClose: () => void;
  initialPrompt: string;
  slotLabel: string;
  onUseImage: (base64: string) => void;
}

const ASPECT_RATIOS = [
  { value: '3:4', label: '3:4 (竖版)' },
  { value: '4:3', label: '4:3 (横版)' },
  { value: '1:1', label: '1:1 (方形)' },
  { value: '16:9', label: '16:9 (宽屏)' },
  { value: '9:16', label: '9:16 (竖屏)' },
];

interface GenerateResponse {
  image_base64: string;
  mime_type: string;
  model: string;
  elapsed: number;
  provider: string;
}

export function ImageGenerateModal({
  open,
  onClose,
  initialPrompt,
  slotLabel,
  onUseImage,
}: ImageGenerateModalProps) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [aspectRatio, setAspectRatio] = useState('3:4');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewBase64, setPreviewBase64] = useState<string | null>(null);
  const [mimeType, setMimeType] = useState('image/png');

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    setPreviewBase64(null);

    try {
      const result = await fetchAPI<GenerateResponse>('/api/ai/generate-image', {
        method: 'POST',
        body: JSON.stringify({ prompt, aspect_ratio: aspectRatio }),
      });
      setPreviewBase64(result.image_base64);
      setMimeType(result.mime_type);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败');
    } finally {
      setLoading(false);
    }
  }, [prompt, aspectRatio]);

  const handleUse = useCallback(() => {
    if (previewBase64) {
      onUseImage(previewBase64);
      onClose();
    }
  }, [previewBase64, onUseImage, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-lg rounded-2xl border border-white/[0.08] bg-[#1a1a2e] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white/90">
            生成图片 — {slotLabel}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-white/40 transition-colors hover:bg-white/[0.08] hover:text-white/70"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Prompt textarea */}
        <label className="mb-1 block text-xs font-medium text-white/40">提示词 (visual_reference)</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          className="mb-4 w-full resize-none rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white/90 placeholder-white/20 outline-none transition-colors focus:border-white/[0.15] focus:ring-1 focus:ring-white/[0.1]"
          placeholder="输入视觉参考描述..."
        />

        {/* Aspect ratio */}
        <label className="mb-1 block text-xs font-medium text-white/40">宽高比</label>
        <div className="mb-4 flex flex-wrap gap-2">
          {ASPECT_RATIOS.map((ar) => (
            <button
              key={ar.value}
              type="button"
              onClick={() => setAspectRatio(ar.value)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                aspectRatio === ar.value
                  ? 'bg-brand/20 text-brand ring-1 ring-brand/30'
                  : 'bg-white/[0.04] text-white/50 hover:bg-white/[0.08] hover:text-white/70'
              }`}
            >
              {ar.label}
            </button>
          ))}
        </div>

        {/* Preview area */}
        {(previewBase64 || loading) && (
          <div className="mb-4 flex items-center justify-center rounded-lg border border-white/[0.06] bg-black/30 p-4" style={{ minHeight: 200 }}>
            {loading ? (
              <div className="flex flex-col items-center gap-2">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/10 border-t-brand" />
                <span className="text-xs text-white/30">生成中...</span>
              </div>
            ) : previewBase64 ? (
              <img
                src={`data:${mimeType};base64,${previewBase64}`}
                alt="Generated preview"
                className="max-h-[300px] rounded-lg object-contain"
              />
            ) : null}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-white/50 transition-colors hover:bg-white/[0.06] hover:text-white/70"
          >
            取消
          </button>
          {previewBase64 ? (
            <button
              type="button"
              onClick={handleUse}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-light"
            >
              使用此图
            </button>
          ) : (
            <button
              type="button"
              onClick={handleGenerate}
              disabled={loading || !prompt.trim()}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-light disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? '生成中...' : '生成'}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
