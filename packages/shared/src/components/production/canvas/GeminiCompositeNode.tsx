/**
 * GeminiCompositeNode — Gemini image generation from 3D stage screenshots.
 *
 * Takes scene screenshot + per-character screenshots + reference photos from
 * upstream DirectorStage3D, builds interleaved parts prompt, calls backend API,
 * outputs final composited image.
 */

'use client';

import { memo, useCallback, useMemo, useState } from 'react';
import { Handle, Position, useEdges, useNodes, useReactFlow, type NodeProps } from '@xyflow/react';
import type { GeminiCompositeNodeData } from '../../../types/canvas';
import { buildInterleavedParts, type StageScreenshots } from '../../panorama/stageScreenshot';
import { API_BASE_URL, normalizeStorageUrl } from '../../../lib/api';

const STATUS_COLORS: Record<string, string> = {
  idle: 'border-zinc-700',
  queued: 'border-blue-500',
  running: 'border-blue-400 animate-pulse',
  success: 'border-emerald-500',
  error: 'border-red-500',
};

function GeminiCompositeNodeInner({ id, data }: NodeProps) {
  const d = data as unknown as GeminiCompositeNodeData;
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const { setNodes } = useReactFlow();
  const edges = useEdges();

  const statusClass = STATUS_COLORS[d.status] || STATUS_COLORS.idle;
  const hasOutput = !!d.outputImageUrl || !!d.outputImageBase64;
  const hasInput = !!d.sceneScreenshotBase64 || !!d.sceneScreenshotStorageKey;
  const inputPreviewSrc = d.sceneScreenshotBase64
    ? `data:image/jpeg;base64,${d.sceneScreenshotBase64}`
    : d.sceneScreenshotStorageKey
      ? `${API_BASE_URL}/uploads/${d.sceneScreenshotStorageKey}`
      : '';

  const handleGenerate = useCallback(async () => {
    if (!hasInput) return;

    // Helper: fetch image from URL → base64
    const fetchAsBase64 = async (url: string): Promise<string> => {
      const resp = await fetch(url);
      if (!resp.ok) return '';
      const blob = await resp.blob();
      return new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const result = reader.result as string;
          resolve(result.includes(',') ? result.split(',')[1] : result);
        };
        reader.readAsDataURL(blob);
      });
    };

    // Update status to running
    setNodes(nds =>
      nds.map(n =>
        n.id === id ? { ...n, data: { ...n.data, status: 'running', progress: 0 } } : n,
      ),
    );
    setErrorMsg(null);

    try {
      // Get scene base64 — from data or fetch from storage
      let sceneBase64 = d.sceneScreenshotBase64 || '';
      if (!sceneBase64 && d.sceneScreenshotStorageKey) {
        sceneBase64 = await fetchAsBase64(`${API_BASE_URL}/uploads/${d.sceneScreenshotStorageKey}`);
      }
      if (!sceneBase64) throw new Error('场景截图不可用');

      // Build StageScreenshots — fetch pose screenshots from storage if base64 missing
      const mappings = d.characterMappings || [];
      const charScreenshots = await Promise.all(
        mappings.map(async m => {
          let pose = m.poseScreenshot || '';
          if (!pose && m.poseStorageKey) {
            pose = await fetchAsBase64(`${API_BASE_URL}/uploads/${m.poseStorageKey}`);
          }
          return {
            stageCharId: m.stageCharId,
            stageCharName: m.stageCharName,
            color: m.color,
            screenshot: pose,
          };
        }),
      );

      const screenshots: StageScreenshots = {
        base: sceneBase64,
        characters: charScreenshots,
      };

      // Fetch reference images from URLs and convert to base64
      const charDataPromises = mappings
        .filter((_m, i) => charScreenshots[i].screenshot) // Must have pose screenshot
        .map(async (m, i) => {
          let referenceBase64 = '';
          if (m.referenceImageUrl) {
            try {
              const normalizedUrl = normalizeStorageUrl(m.referenceImageUrl);
              referenceBase64 = await fetchAsBase64(normalizedUrl);
            } catch {
              // Reference image fetch failed, continue without it
            }
          }
          return {
            stageCharId: m.stageCharId,
            referenceCharName: m.stageCharName,
            stageCharColor: m.color,
            poseScreenshot: charScreenshots[i].screenshot,
            referenceBase64,
            bbox: m.bbox,
          };
        });

      const charData = (await Promise.all(charDataPromises))
        .filter(cd => cd.referenceBase64); // Only include chars with reference photos

      // Build parts (frontend constructs text prompt; images sent as references)
      const parts = buildInterleavedParts(screenshots, charData, d.sceneDescription);

      // Call backend
      const resp = await fetch(`${API_BASE_URL}/api/ai/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: '根据提供的图片生成高品质画面',
          interleaved_parts: parts.map(p => ({
            type: p.type,
            content: p.content,
            mime_type: p.mime_type,
          })),
          aspect_ratio: '16:9',
          image_size: '2K',
        }),
      });

      if (!resp.ok) {
        const errBody = await resp.text();
        throw new Error(`生成失败 (${resp.status}): ${errBody}`);
      }

      const result = await resp.json();
      const outputUrl = normalizeStorageUrl(result.storage_uri) || undefined;

      // Update with output
      setNodes(nds =>
        nds.map(n => {
          if (n.id === id) {
            return {
              ...n,
              data: {
                ...n.data,
                outputImageBase64: result.image_base64,
                outputStorageKey: result.storage_key,
                outputImageUrl: outputUrl,
                status: 'success',
                progress: 100,
              },
            };
          }
          // Propagate to downstream PostExpression
          const downEdge = edges.find(e => e.source === id && e.target === n.id);
          if (downEdge && (n.data as Record<string, unknown>).nodeType === 'imageProcess') {
            return {
              ...n,
              data: {
                ...n.data,
                inputImageUrl: outputUrl || `data:image/jpeg;base64,${result.image_base64}`,
                inputStorageKey: result.storage_key,
                status: 'idle',
              },
            };
          }
          return n;
        }),
      );

      // Persist result to backend for restore after refresh
      fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_type: 'geminiComposite',
          content: {
            storage_key: result.storage_key,
            storage_uri: result.storage_uri,
            sceneScreenshotStorageKey: d.sceneScreenshotStorageKey,
            characterMappings: d.characterMappings?.map(m => ({
              stageCharId: m.stageCharId,
              stageCharName: m.stageCharName,
              color: m.color,
              poseStorageKey: m.poseStorageKey,
              referenceImageUrl: m.referenceImageUrl,
              referenceStorageKey: m.referenceStorageKey,
              bbox: m.bbox,
            })),
            sceneDescription: d.sceneDescription,
          },
        }),
      }).catch(() => {});
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setNodes(nds =>
        nds.map(n =>
          n.id === id
            ? { ...n, data: { ...n.data, status: 'error', errorMessage: msg } }
            : n,
        ),
      );
    }
  }, [hasInput, id, d, edges, setNodes]);

  return (
    <div
      className={`relative rounded-lg border-2 bg-zinc-900 text-white shadow-lg ${statusClass}`}
      style={{ width: 280, minHeight: 180 }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Left} className="!bg-purple-500 !w-3 !h-3" />
      <Handle type="source" position={Position.Right} className="!bg-purple-500 !w-3 !h-3" />

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-700">
        <span className="text-sm font-medium">Gemini合成</span>
        <span className="ml-auto text-xs text-zinc-400">{d.status}</span>
      </div>

      {/* Body */}
      <div className="p-3">
        {hasOutput ? (
          <div className="flex flex-col gap-2">
            <img
              src={d.outputImageUrl || `data:image/jpeg;base64,${d.outputImageBase64}`}
              alt="Gemini合成结果"
              className="w-full rounded object-cover"
              style={{ maxHeight: 140 }}
            />
            <button
              onClick={handleGenerate}
              disabled={d.status === 'running'}
              className="w-full py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 disabled:bg-zinc-800 disabled:cursor-not-allowed text-xs font-medium transition-colors"
            >
              {d.status === 'running' ? '生成中...' : '重新生成'}
            </button>
          </div>
        ) : hasInput ? (
          <div className="flex flex-col gap-2">
            <img
              src={inputPreviewSrc}
              alt="场景截图"
              className="w-full rounded object-cover opacity-60"
              style={{ maxHeight: 100 }}
            />
            <button
              onClick={handleGenerate}
              disabled={d.status === 'running'}
              className="w-full py-1.5 rounded bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-700 disabled:cursor-not-allowed text-xs font-medium transition-colors"
            >
              {d.status === 'running' ? '生成中...' : '生成影视级画面'}
            </button>
          </div>
        ) : (
          <div
            className="flex flex-col items-center justify-center gap-2 rounded bg-zinc-800"
            style={{ height: 100 }}
          >
            <span className="text-xs text-zinc-500">等待3D导演台截图</span>
          </div>
        )}

        {/* Error message */}
        {errorMsg && (
          <div className="mt-2 text-xs text-red-400 break-all">{errorMsg}</div>
        )}

        {/* Character mappings indicator */}
        {d.characterMappings && d.characterMappings.length > 0 && (
          <div className="mt-2 flex gap-1 flex-wrap">
            {d.characterMappings.map((m, i) => (
              <span
                key={i}
                className="text-xs px-1.5 py-0.5 rounded"
                style={{ backgroundColor: m.color, color: '#fff' }}
              >
                {m.stageCharName}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export const GeminiCompositeNode = memo(GeminiCompositeNodeInner);
