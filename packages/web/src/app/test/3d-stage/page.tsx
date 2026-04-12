'use client';

import { useState, useRef, useCallback } from 'react';
import { ParallaxStage3D } from '@unrealmake/shared/components/panorama/ParallaxStage3D';
import { createStageCharacter } from '@unrealmake/shared/components/panorama/stageCharacter';
import type { StageCharacter } from '@unrealmake/shared/components/panorama/stageCharacter';
import type { StageScreenshots, GeminiPart } from '@unrealmake/shared/components/panorama/stageScreenshot';
import { buildGeminiPrompt, buildImageList, buildMappings, buildInterleavedParts } from '@unrealmake/shared/components/panorama/stageScreenshot';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Step state ────────────────────────────────────────────────────

type Step =
  | 'prompt'
  | 'generating-ref'
  | 'ref-ready'
  | 'generating-vr'
  | 'vr-ready'
  | 'generating-depth'
  | 'depth-ready'
  | 'stage'
  | 'screenshots-ready'
  | 'generating-final'
  | 'final-ready';

// ── Depth prompt ─────────────────────────────────────────────────

const DEPTH_PROMPT =
  'Generate a depth map of this image. Output a single-channel grayscale image. ' +
  'White (255) = closest to camera, Black (0) = farthest from camera. ' +
  'The depth map should accurately represent the 3D spatial structure of the scene ' +
  'with smooth, continuous depth transitions. No text, no labels, no color — pure grayscale depth only.';

// ── Character ref type ──────────────────────────────────────────

interface CharRef {
  charId: string;
  name: string;
  imageUrl: string;      // display URL
  imageBase64: string;   // for Gemini
  assignedTo: string;    // stage char id
}

// ── Styles ────────────────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 12, padding: '16px 20px', width: '100%', maxWidth: 700,
};
const btnPrimary = (enabled: boolean): React.CSSProperties => ({
  padding: '10px 24px', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: enabled ? 'pointer' : 'default',
  background: enabled ? 'rgba(6,182,212,0.3)' : 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(6,182,212,0.4)',
  color: enabled ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.3)',
});
const btnSecondary: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 8, fontSize: 12, cursor: 'pointer',
  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
  color: 'rgba(255,255,255,0.6)',
};
const labelStyle: React.CSSProperties = {
  fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: 1, marginBottom: 8, display: 'block',
};
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px', borderRadius: 8,
  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
  color: '#fff', fontSize: 13, outline: 'none', resize: 'vertical',
};
const imgPreviewStyle: React.CSSProperties = {
  width: '100%', maxHeight: 260, objectFit: 'contain', borderRadius: 8,
  background: 'rgba(0,0,0,0.3)', marginTop: 8,
};

// ══════════════════════════════════════════════════════════════════

export default function Test3DStagePage() {
  const [step, setStep] = useState<Step>('prompt');
  const [prompt, setPrompt] = useState('一个宽敞的中式古典大厅，红木柱子，雕花屏风，阳光从高窗洒入');
  const [stylePreset, setStylePreset] = useState('realistic');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState({ ref: 0, vr: 0, depth: 0, final: 0 });

  // Reference image
  const [refBase64, setRefBase64] = useState('');
  const [refStorageKey, setRefStorageKey] = useState('');

  // VR panorama
  const [vrBase64, setVrBase64] = useState('');
  const [vrMime, setVrMime] = useState('image/png');
  const [vrUrl, setVrUrl] = useState('');

  // Depth map
  const [depthBase64, setDepthBase64] = useState('');
  const [depthUrl, setDepthUrl] = useState('');

  // 3D Stage
  const [stageOpen, setStageOpen] = useState(false);
  const [stageChars, setStageChars] = useState<StageCharacter[]>([]);

  // Character references
  const [projectId, setProjectId] = useState('');
  const [charRefs, setCharRefs] = useState<CharRef[]>([]);
  const [loadingChars, setLoadingChars] = useState(false);

  // Screenshots
  const [screenshots, setScreenshots] = useState<StageScreenshots | null>(null);

  // Final generation
  const [finalBase64, setFinalBase64] = useState('');

  // Direct file upload
  const vrFileRef = useRef<HTMLInputElement>(null);
  const depthFileRef = useRef<HTMLInputElement>(null);
  const [directVrUrl, setDirectVrUrl] = useState('');
  const [directDepthUrl, setDirectDepthUrl] = useState('');

  // ── Helper ──
  const base64ToBlob = (b64: string, mime: string): Blob => {
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new Blob([arr], { type: mime });
  };

  // ── Load characters from project ──
  const handleLoadChars = useCallback(async () => {
    if (!projectId.trim()) return;
    setLoadingChars(true);
    setError('');
    try {
      // Fetch characters
      const charResp = await fetch(`${API}/api/projects/${projectId}/characters`);
      if (!charResp.ok) throw new Error(`获取角色失败 (${charResp.status})`);
      const characters: Array<{ id: string; name: string }> = await charResp.json();

      // Fetch asset images
      const imgResp = await fetch(`${API}/api/projects/${projectId}/asset-images`);
      if (!imgResp.ok) throw new Error(`获取角色图片失败 (${imgResp.status})`);
      const images: Array<{ asset_id: string; asset_type: string; slot_key: string; storage_key: string }> = await imgResp.json();

      // Build char refs — pick first image per character
      const refs: CharRef[] = [];
      for (const char of characters) {
        const img = images.find(i => i.asset_id === char.id && i.asset_type === 'character');
        if (img) {
          // Fetch image as base64 for Gemini
          const imgUrl = `${API}/uploads/${img.storage_key}`;
          let b64 = '';
          try {
            const blobResp = await fetch(imgUrl);
            const blob = await blobResp.blob();
            b64 = await new Promise<string>((resolve) => {
              const reader = new FileReader();
              reader.onload = () => resolve((reader.result as string).split(',')[1] || '');
              reader.readAsDataURL(blob);
            });
          } catch { /* skip if image can't be loaded */ }

          refs.push({
            charId: char.id,
            name: char.name,
            imageUrl: imgUrl,
            imageBase64: b64,
            assignedTo: '',
          });
        }
      }
      setCharRefs(refs);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingChars(false);
    }
  }, [projectId]);

  // ── Assign character ref to stage mannequin ──
  const handleAssign = useCallback((charRefIdx: number, stageCharId: string) => {
    setCharRefs(prev => prev.map((r, i) => i === charRefIdx ? { ...r, assignedTo: stageCharId } : r));
  }, []);

  // ── Create stage characters from assigned refs ──
  const buildStageChars = useCallback((): StageCharacter[] => {
    const assigned = charRefs.filter(r => r.assignedTo);
    if (assigned.length === 0) {
      // Default: 2 characters
      return [createStageCharacter(0), createStageCharacter(1)];
    }
    return assigned.map((ref, i) => {
      const base = createStageCharacter(i);
      return { ...base, id: ref.assignedTo || base.id, name: ref.name };
    });
  }, [charRefs]);

  // ── Step 1: Generate reference image ──
  const handleGenerateRef = useCallback(async () => {
    if (!prompt.trim()) return;
    setStep('generating-ref');
    setError('');
    try {
      const resp = await fetch(`${API}/api/ai/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), aspect_ratio: '16:9', image_size: '2K' }),
      });
      if (!resp.ok) throw new Error(`生成参考图失败 (${resp.status}): ${await resp.text()}`);
      const data = await resp.json();
      setRefBase64(data.image_base64);
      setRefStorageKey(data.storage_key || '');
      setElapsed(prev => ({ ...prev, ref: data.elapsed || 0 }));
      setStep('ref-ready');
    } catch (e: any) {
      setError(e.message); setStep('prompt');
    }
  }, [prompt]);

  // ── Step 2: Generate VR panorama ──
  const handleGenerateVR = useCallback(async () => {
    if (!refStorageKey) { setError('缺少参考图 storage_key'); return; }
    setStep('generating-vr');
    setError('');
    try {
      const resp = await fetch(`${API}/api/ai/generate-panorama`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reference_storage_key: refStorageKey,
          prompt: prompt.trim(),
          style_preset: stylePreset,
        }),
      });
      if (!resp.ok) throw new Error(`生成 VR 全景失败 (${resp.status}): ${await resp.text()}`);
      const data = await resp.json();
      setVrBase64(data.image_base64);
      setVrMime(data.mime_type || 'image/png');
      setElapsed(prev => ({ ...prev, vr: data.elapsed || 0 }));

      const url = data.storage_key
        ? `${API}/uploads/${data.storage_key}`
        : `data:${data.mime_type};base64,${data.image_base64}`;
      setVrUrl(url);
      setStep('vr-ready');
    } catch (e: any) {
      setError(e.message); setStep('ref-ready');
    }
  }, [refStorageKey, prompt, stylePreset]);

  // ── Step 3: Generate depth map from VR panorama ──
  const handleGenerateDepth = useCallback(async () => {
    if (!vrBase64) { setError('缺少 VR 全景图'); return; }
    setStep('generating-depth');
    setError('');
    try {
      const blob = base64ToBlob(vrBase64, vrMime);
      const ext = vrMime.includes('jpeg') || vrMime.includes('jpg') ? 'jpg' : 'png';
      const formData = new FormData();
      formData.append('prompt', DEPTH_PROMPT);
      formData.append('aspect_ratio', '2:1');
      formData.append('image_size', '2K');
      formData.append('reference', new File([blob], `vr_panorama.${ext}`, { type: vrMime }));

      const resp = await fetch(`${API}/api/ai/generate-image/upload`, {
        method: 'POST',
        body: formData,
      });
      if (!resp.ok) throw new Error(`生成深度图失败 (${resp.status}): ${await resp.text()}`);
      const data = await resp.json();
      setDepthBase64(data.image_base64);
      setElapsed(prev => ({ ...prev, depth: data.elapsed || 0 }));
      setDepthUrl(`data:${data.mime_type || 'image/png'};base64,${data.image_base64}`);
      setStep('depth-ready');
    } catch (e: any) {
      setError(e.message); setStep('vr-ready');
    }
  }, [vrBase64, vrMime]);

  // ── Step 4: Open 3D Stage ──
  const handleOpenStage = useCallback(() => {
    const chars = buildStageChars();
    setStageChars(chars);
    setStep('stage');
    setStageOpen(true);
  }, [buildStageChars]);

  // ── Screenshots callback ──
  const handleScreenshots = useCallback((ss: StageScreenshots) => {
    setScreenshots(ss);
    setStageOpen(false);
    setStep('screenshots-ready');
  }, []);

  // ── Step 6: Generate final image ──
  const handleGenerateFinal = useCallback(async () => {
    if (!screenshots) return;
    setStep('generating-final');
    setError('');
    try {
      const assigned = charRefs.filter(r => r.assignedTo);

      // Match each screenshot character to a reference — by ID, then name, then index
      const characterData = screenshots.characters.map((cs, i) => {
        const ref = assigned.find(r => r.assignedTo === cs.stageCharId)
          || assigned.find(r => r.name === cs.stageCharName)
          || assigned[i];
        return {
          stageCharId: cs.stageCharId,
          referenceCharName: ref?.name || cs.stageCharName,
          stageCharColor: cs.color,
          poseScreenshot: cs.screenshot,
          referenceBase64: ref?.imageBase64 || '',
        };
      }).filter(cd => cd.referenceBase64); // only include chars with reference photos

      // Build interleaved parts (text → image → text → image → ... → instruction)
      const interleavedParts = buildInterleavedParts(screenshots, characterData, prompt);

      // Convert to API format
      const apiParts = interleavedParts.map(p => ({
        type: p.type,
        content: p.content,
        mime_type: p.mime_type || 'image/jpeg',
      }));

      // Debug: log parts summary
      let totalB64 = 0;
      for (const p of apiParts) {
        if (p.type === 'image') {
          totalB64 += p.content.length;
          console.log(`[STAGE-DEBUG] Image part: ${(p.content.length / 1024).toFixed(0)}KB base64 (~${(p.content.length * 3 / 4 / 1024).toFixed(0)}KB raw)`);
        } else {
          console.log(`[STAGE-DEBUG] Text part: ${p.content.length} chars`);
          console.log(`[STAGE-DEBUG] Text content:\n${p.content}`);
        }
      }
      console.log(`[STAGE-DEBUG] Total ${apiParts.length} parts, total image base64: ${(totalB64 / 1024 / 1024).toFixed(2)}MB`);

      const resp = await fetch(`${API}/api/ai/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: '根据提供的图片生成影视级画面',  // fallback prompt (interleaved_parts takes priority)
          aspect_ratio: '16:9',
          image_size: '2K',
          interleaved_parts: apiParts,
        }),
      });

      if (!resp.ok) throw new Error(`生成最终图失败 (${resp.status}): ${await resp.text()}`);
      const data = await resp.json();
      setFinalBase64(data.image_base64);
      setElapsed(prev => ({ ...prev, final: data.elapsed || 0 }));
      setStep('final-ready');
    } catch (e: any) {
      setError(e.message);
      setStep('screenshots-ready');
    }
  }, [screenshots, charRefs, prompt]);

  // ── Direct upload ──
  const handleDirectOpen = useCallback(() => {
    if (!directVrUrl || !directDepthUrl) return;
    setVrUrl(directVrUrl); setDepthUrl(directDepthUrl);
    const chars = buildStageChars();
    setStageChars(chars);
    setStep('stage'); setStageOpen(true);
  }, [directVrUrl, directDepthUrl, buildStageChars]);

  const handleVrFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setDirectVrUrl(URL.createObjectURL(file));
  }, []);
  const handleDepthFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setDirectDepthUrl(URL.createObjectURL(file));
  }, []);

  // ── Reset ──
  const handleReset = useCallback(() => {
    setStep('prompt'); setError('');
    setRefBase64(''); setRefStorageKey('');
    setVrBase64(''); setVrUrl('');
    setDepthBase64(''); setDepthUrl('');
    setStageOpen(false); setScreenshots(null); setFinalBase64('');
  }, []);

  const Spinner = ({ text }: { text: string }) => (
    <div style={{ textAlign: 'center', padding: '40px 0' }}>
      <div style={{ fontSize: 20, marginBottom: 8, animation: 'spin 1s linear infinite' }}>&#9696;</div>
      <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)' }}>{text}</div>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );

  // ── Step index for progress bar ──
  const STEPS = ['1. 提示词', '2. 参考图', '3. VR 全景', '4. 深度图', '5. 3D 导演台', '6. 截图', '7. 生图'];
  const stepIdx =
    step === 'generating-ref' || step === 'ref-ready' ? 1 :
    step === 'generating-vr' || step === 'vr-ready' ? 2 :
    step === 'generating-depth' || step === 'depth-ready' ? 3 :
    step === 'stage' ? 4 :
    step === 'screenshots-ready' ? 5 :
    step === 'generating-final' || step === 'final-ready' ? 6 : 0;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 20px' }}>
      <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 4, color: 'rgba(255,255,255,0.9)' }}>
        3D 导演台 — 视差方案
      </h1>
      <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', marginBottom: 32, textAlign: 'center' }}>
        提示词 → 参考图 → VR 全景 → 深度图 → 3D 导演台 → 截图 → Gemini 生图
      </p>

      {/* Progress bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 28, width: '100%', maxWidth: 700 }}>
        {STEPS.map((label, i) => (
          <div key={label} style={{ flex: 1, textAlign: 'center' }}>
            <div style={{
              height: 3, borderRadius: 2, marginBottom: 6,
              background: i <= stepIdx ? 'rgba(6,182,212,0.8)' : 'rgba(255,255,255,0.08)',
              transition: 'background 0.3s',
            }} />
            <span style={{ fontSize: 9, color: i <= stepIdx ? 'rgba(6,182,212,0.8)' : 'rgba(255,255,255,0.25)' }}>
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div style={{
          ...cardStyle, marginBottom: 16,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: 'rgba(239,68,68,0.9)', fontSize: 12,
        }}>{error}</div>
      )}

      {/* ═══ Character loading panel (always visible before stage) ═══ */}
      {!['stage', 'screenshots-ready', 'generating-final', 'final-ready'].includes(step) && (
        <div style={{ ...cardStyle, marginBottom: 16, border: '1px solid rgba(168,85,247,0.15)' }}>
          <span style={{ ...labelStyle, color: 'rgba(168,85,247,0.5)' }}>角色参考（从项目加载）</span>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <input
              value={projectId} onChange={e => setProjectId(e.target.value)}
              placeholder="输入项目 ID（UUID）"
              style={{ ...inputStyle, flex: 1 }}
            />
            <button onClick={handleLoadChars} disabled={loadingChars || !projectId.trim()} style={btnPrimary(!!projectId.trim())}>
              {loadingChars ? '加载中...' : '加载角色'}
            </button>
          </div>
          {charRefs.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {charRefs.map((ref, i) => (
                <div key={ref.charId} style={{
                  flex: '0 0 calc(50% - 5px)', background: 'rgba(255,255,255,0.03)',
                  borderRadius: 8, padding: 8, border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', marginBottom: 4 }}>{ref.name}</div>
                  {ref.imageUrl && (
                    <img src={ref.imageUrl} alt={ref.name} style={{
                      width: '100%', height: 80, objectFit: 'cover', borderRadius: 6, marginBottom: 6,
                    }} />
                  )}
                  <select
                    value={ref.assignedTo}
                    onChange={e => handleAssign(i, e.target.value)}
                    style={{
                      width: '100%', padding: '4px 6px', borderRadius: 4, fontSize: 10,
                      background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                      color: '#fff',
                    }}
                  >
                    <option value="">未分配</option>
                    <option value={`char_${i}`}>角色 {i + 1}</option>
                    {charRefs.map((_, j) => j !== i ? (
                      <option key={j} value={`char_${j}`}>角色 {j + 1}</option>
                    ) : null)}
                  </select>
                </div>
              ))}
            </div>
          )}
          {charRefs.length === 0 && !loadingChars && (
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', textAlign: 'center', padding: '8px 0' }}>
              输入项目 ID 加载角色参考图，或直接进入导演台
            </div>
          )}
        </div>
      )}

      {/* ═══ Step 1: Prompt ═══ */}
      {(step === 'prompt' || step === 'generating-ref') && (
        <div style={cardStyle}>
          <span style={labelStyle}>STEP 1 — 场景描述</span>
          <textarea
            value={prompt} onChange={e => setPrompt(e.target.value)}
            rows={3} placeholder="描述你想要的场景..."
            style={{ ...inputStyle, marginBottom: 12 }}
            disabled={step === 'generating-ref'}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>风格:</span>
            {['realistic', 'cinematic', '3d_chinese', 'anime'].map(s => (
              <button key={s} onClick={() => setStylePreset(s)} style={{
                padding: '3px 10px', borderRadius: 4, fontSize: 10, cursor: 'pointer',
                background: stylePreset === s ? 'rgba(6,182,212,0.2)' : 'rgba(255,255,255,0.04)',
                border: stylePreset === s ? '1px solid rgba(6,182,212,0.4)' : '1px solid rgba(255,255,255,0.08)',
                color: stylePreset === s ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.4)',
              }}>{s}</button>
            ))}
          </div>
          {step === 'generating-ref' ? <Spinner text="正在生成参考图..." /> : (
            <button onClick={handleGenerateRef} disabled={!prompt.trim()} style={btnPrimary(!!prompt.trim())}>
              生成参考图
            </button>
          )}
        </div>
      )}

      {/* ═══ Step 2: Ref ready → VR ═══ */}
      {(step === 'ref-ready' || step === 'generating-vr') && (
        <div style={cardStyle}>
          <span style={labelStyle}>STEP 2 — 参考图 → VR 全景</span>
          {refBase64 && <img src={`data:image/png;base64,${refBase64}`} alt="参考图" style={imgPreviewStyle} />}
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 8, marginBottom: 12 }}>
            参考图生成耗时 {elapsed.ref.toFixed(1)}s
          </div>
          {step === 'generating-vr' ? <Spinner text="正在生成 VR 全景（30-60s）..." /> : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleGenerateVR} style={btnPrimary(true)}>生成 VR 全景</button>
              <button onClick={() => setStep('prompt')} style={btnSecondary}>返回修改</button>
            </div>
          )}
        </div>
      )}

      {/* ═══ Step 3: VR ready → Depth ═══ */}
      {(step === 'vr-ready' || step === 'generating-depth') && (
        <div style={cardStyle}>
          <span style={labelStyle}>STEP 3 — VR 全景 → 深度图</span>
          {vrBase64 && <img src={`data:${vrMime};base64,${vrBase64}`} alt="VR 全景" style={imgPreviewStyle} />}
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 8, marginBottom: 12 }}>
            VR 全景生成耗时 {elapsed.vr.toFixed(1)}s
          </div>
          {step === 'generating-depth' ? <Spinner text="正在通过 Gemini 生成深度图..." /> : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleGenerateDepth} style={btnPrimary(true)}>生成深度图</button>
              <button onClick={() => setStep('ref-ready')} style={btnSecondary}>重新生成 VR</button>
            </div>
          )}
        </div>
      )}

      {/* ═══ Step 4: Depth ready → 3D ═══ */}
      {step === 'depth-ready' && (
        <div style={cardStyle}>
          <span style={labelStyle}>STEP 4 — 深度图 → 视差 3D 导演台</span>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>VR 全景</div>
              {vrBase64 && <img src={`data:${vrMime};base64,${vrBase64}`} alt="VR" style={{ ...imgPreviewStyle, marginTop: 0 }} />}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>深度图</div>
              {depthBase64 && <img src={`data:image/png;base64,${depthBase64}`} alt="深度" style={{ ...imgPreviewStyle, marginTop: 0 }} />}
            </div>
          </div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 8, marginBottom: 12 }}>
            深度图生成耗时 {elapsed.depth.toFixed(1)}s
            {charRefs.filter(r => r.assignedTo).length > 0 && (
              <span> | 已分配 {charRefs.filter(r => r.assignedTo).length} 个角色</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleOpenStage} style={btnPrimary(true)}>打开 3D 导演台</button>
            <button onClick={() => setStep('vr-ready')} style={btnSecondary}>重新生成深度图</button>
            <button onClick={handleReset} style={btnSecondary}>从头开始</button>
          </div>
        </div>
      )}

      {/* ═══ Stage closed (no screenshots yet) ═══ */}
      {step === 'stage' && !stageOpen && (
        <div style={cardStyle}>
          <span style={labelStyle}>3D 导演台已关闭（未截图）</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setStageOpen(true)} style={btnPrimary(true)}>重新打开</button>
            <button onClick={handleReset} style={btnSecondary}>从头开始</button>
          </div>
        </div>
      )}

      {/* ═══ Step 6: Screenshots ready → Generate ═══ */}
      {(step === 'screenshots-ready' || step === 'generating-final') && screenshots && (
        <div style={cardStyle}>
          <span style={labelStyle}>STEP 6 — 截图完成 → Gemini 生图</span>

          {/* Base screenshot */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>全场景截图</div>
            <img src={`data:image/jpeg;base64,${screenshots.base}`} alt="全场景" style={{ ...imgPreviewStyle, marginTop: 0 }} />
          </div>

          {/* Per-character screenshots + reference */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            {screenshots.characters.map(cs => {
              const ref = charRefs.find(r => r.assignedTo === cs.stageCharId)
                || charRefs.find(r => r.name === cs.stageCharName);
              return (
                <div key={cs.stageCharId} style={{
                  flex: '1 1 calc(50% - 4px)', background: 'rgba(255,255,255,0.03)',
                  borderRadius: 8, padding: 8, border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ fontSize: 10, color: cs.color, marginBottom: 4 }}>
                    {cs.stageCharName} {ref ? `→ ${ref.name}` : '(未分配角色)'}
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.25)', marginBottom: 2 }}>3D 姿态</div>
                      <img src={`data:image/jpeg;base64,${cs.screenshot}`} alt="pose" style={{
                        width: '100%', height: 80, objectFit: 'contain', borderRadius: 4, background: 'rgba(0,0,0,0.3)',
                      }} />
                    </div>
                    {ref && (
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.25)', marginBottom: 2 }}>参考形象</div>
                        <img src={ref.imageUrl} alt="ref" style={{
                          width: '100%', height: 80, objectFit: 'cover', borderRadius: 4,
                        }} />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Prompt preview — show parts structure (images first, then text) */}
          {charRefs.filter(r => r.assignedTo).length > 0 && screenshots && (
            <details style={{ marginBottom: 12 }}>
              <summary style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', cursor: 'pointer' }}>
                查看 Gemini 提示词（图1-图N + 文本指令）
              </summary>
              <div style={{
                fontSize: 9, color: 'rgba(255,255,255,0.4)', background: 'rgba(0,0,0,0.3)',
                padding: 8, borderRadius: 6, marginTop: 4,
              }}>
                {(() => {
                  const assigned = charRefs.filter(r => r.assignedTo);
                  const charData = screenshots.characters.map((cs, i) => {
                    const ref = assigned.find(r => r.assignedTo === cs.stageCharId)
                      || assigned.find(r => r.name === cs.stageCharName)
                      || assigned[i];
                    return {
                      stageCharId: cs.stageCharId,
                      referenceCharName: ref?.name || cs.stageCharName,
                      stageCharColor: cs.color,
                      poseScreenshot: cs.screenshot,
                      referenceBase64: ref?.imageBase64 || '',
                    };
                  }).filter(cd => cd.referenceBase64);
                  const parts = buildInterleavedParts(screenshots, charData, prompt);
                  return parts.map((p, i) => (
                    <div key={i} style={{ marginBottom: 4, padding: '2px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <span style={{ color: p.type === 'text' ? 'rgba(6,182,212,0.6)' : 'rgba(168,85,247,0.6)', marginRight: 6 }}>
                        [{p.type === 'text' ? '文本' : '图片'}]
                      </span>
                      {p.type === 'text' ? (
                        <span style={{ whiteSpace: 'pre-wrap' }}>{p.content}</span>
                      ) : (
                        <span style={{ color: 'rgba(168,85,247,0.4)' }}>
                          [base64 图片, {Math.round((p.content?.length || 0) / 1024)}KB]
                        </span>
                      )}
                    </div>
                  ));
                })()}
              </div>
            </details>
          )}

          {step === 'generating-final' ? <Spinner text="Gemini 生成最终画面中..." /> : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handleGenerateFinal}
                disabled={charRefs.filter(r => r.assignedTo).length === 0}
                style={btnPrimary(charRefs.filter(r => r.assignedTo).length > 0)}
              >
                生成最终画面
              </button>
              <button onClick={() => { setStageOpen(true); setStep('stage'); }} style={btnSecondary}>
                重新调整
              </button>
              <button onClick={handleReset} style={btnSecondary}>从头开始</button>
            </div>
          )}
        </div>
      )}

      {/* ═══ Step 7: Final result ═══ */}
      {step === 'final-ready' && (
        <div style={cardStyle}>
          <span style={labelStyle}>STEP 7 — 最终生成结果</span>
          {finalBase64 && (
            <img src={`data:image/png;base64,${finalBase64}`} alt="最终结果" style={{ ...imgPreviewStyle, maxHeight: 400 }} />
          )}
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 8, marginBottom: 12 }}>
            生成耗时 {elapsed.final.toFixed(1)}s
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleGenerateFinal} style={btnPrimary(true)}>重新生成</button>
            <button onClick={() => setStep('screenshots-ready')} style={btnSecondary}>调整参数</button>
            <button onClick={handleReset} style={btnSecondary}>从头开始</button>
          </div>
        </div>
      )}

      {/* ── Divider ── */}
      <div style={{
        width: '100%', maxWidth: 700, margin: '28px 0',
        borderTop: '1px solid rgba(255,255,255,0.06)', position: 'relative',
      }}>
        <span style={{
          position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)',
          background: '#000', padding: '0 12px', fontSize: 10, color: 'rgba(255,255,255,0.2)',
        }}>或直接上传 VR 全景 + 深度图</span>
      </div>

      {/* ── Direct upload ── */}
      <div style={{ ...cardStyle, opacity: step.startsWith('generating') ? 0.3 : 1 }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>VR 全景（equirectangular）</div>
            <button onClick={() => vrFileRef.current?.click()} style={{ ...btnSecondary, width: '100%' }}>
              {directVrUrl ? '已选择' : '选择文件'}
            </button>
            <input ref={vrFileRef} type="file" accept="image/*" onChange={handleVrFile} style={{ display: 'none' }} />
            {directVrUrl && <img src={directVrUrl} alt="vr" style={{ ...imgPreviewStyle, maxHeight: 100 }} />}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>深度图（灰度，白=近 黑=远）</div>
            <button onClick={() => depthFileRef.current?.click()} style={{ ...btnSecondary, width: '100%' }}>
              {directDepthUrl ? '已选择' : '选择文件'}
            </button>
            <input ref={depthFileRef} type="file" accept="image/*" onChange={handleDepthFile} style={{ display: 'none' }} />
            {directDepthUrl && <img src={directDepthUrl} alt="depth" style={{ ...imgPreviewStyle, maxHeight: 100 }} />}
          </div>
        </div>
        <button onClick={handleDirectOpen} disabled={!directVrUrl || !directDepthUrl} style={btnPrimary(!!directVrUrl && !!directDepthUrl)}>
          打开 3D 导演台
        </button>
      </div>

      {/* ── Parallax 3D Stage ── */}
      {vrUrl && depthUrl && (
        <ParallaxStage3D
          panoramaUrl={vrUrl}
          depthMapUrl={depthUrl}
          isOpen={stageOpen}
          onClose={() => setStageOpen(false)}
          characters={stageChars.length > 0 ? stageChars : undefined}
          onCharactersUpdate={setStageChars}
          onScreenshots={handleScreenshots}
        />
      )}
    </div>
  );
}
