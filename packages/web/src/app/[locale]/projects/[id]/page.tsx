'use client';

import { useEffect, useCallback, useMemo, useRef, useState } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import {
  useBoardStore,
  useEdition,
  usePreviewStore,
  useProjectStore,
} from '@unrealmake/shared/hooks';
import {
  StageTabs,
  AssetLibraryGrid,
  AssetLibrarySidebar,
  PipelineStatusBar,
  BasicInfoTab,
  PreviewAnimaticWorkspace,
} from '@unrealmake/shared/components';
import dynamic from 'next/dynamic';

import { CanvasSkeleton } from '@unrealmake/shared/components/production/canvas/CanvasSkeleton';
import { ParticleBrandAnimation } from '@unrealmake/shared/components/production/canvas/ParticleBrandAnimation';

const ShotProductionBoard = dynamic(
  () => import('@unrealmake/shared/components/production/ShotProductionBoard').then((m) => ({ default: m.ShotProductionBoard })),
  { ssr: false },
);
import {
  buildAnimaticClips,
  buildSequenceBundle,
  buildShotProductionProjection,
  fetchAPI,
} from '@unrealmake/shared/lib';
import { API_BASE_URL } from '@unrealmake/shared/lib/api';
import type {
  Project, Beat, Scene, Shot, ShotGroup, Character, Location,
  Prop, CharacterVariant, ImportSSEEvent, GeneratedScript, ScriptBeat, ScriptShot,
  SceneStoryboardReadinessReport,
} from '@unrealmake/shared/types';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

type StageTab = 'info' | 'assets' | 'script' | 'canvas' | 'preview';

/* ── Resizable Divider ── */
function ResizeDivider({ onMouseDown }: { onMouseDown: (e: React.MouseEvent) => void }) {
  return (
    <div
      onMouseDown={onMouseDown}
      className="group relative w-0 shrink-0 cursor-col-resize select-none z-10"
    >
      {/* hit area */}
      <div className="absolute inset-y-0 -left-1.5 w-3" />
      {/* visible line */}
      <div className="absolute inset-y-0 left-0 w-px bg-white/[0.06] group-hover:bg-blue-400/50 transition-colors" />
    </div>
  );
}

/* ── Beat type badge colors ── */
const BEAT_TYPE_STYLES: Record<string, string> = {
  hook: 'bg-red-500/20 text-red-300 ring-red-500/30',
  conflict: 'bg-orange-500/20 text-orange-300 ring-orange-500/30',
  reversal: 'bg-purple-500/20 text-purple-300 ring-purple-500/30',
  sweet_spot: 'bg-green-500/20 text-green-300 ring-green-500/30',
  cliffhanger: 'bg-yellow-500/20 text-yellow-300 ring-yellow-500/30',
};

/* ── Structured Script Renderer ── */
function StructuredScriptView({ script }: { script: GeneratedScript }) {
  return (
    <div className="space-y-4">
      {/* Header stats */}
      <div className="flex flex-wrap gap-3 rounded-lg bg-white/[0.03] p-3 ring-1 ring-inset ring-white/[0.06]">
        <div className="text-xs text-white/40">
          时长 <span className="text-white/70">{script.duration_estimate_s}s</span>
        </div>
        <div className="text-xs text-white/40">
          字数 <span className="text-white/70">{script.total_word_count}</span>
        </div>
        <div className="text-xs text-white/40">
          对白占比 <span className={`font-medium ${script.dialogue_ratio >= 0.3 && script.dialogue_ratio <= 0.4 ? 'text-green-300/80' : 'text-red-300/80'}`}>
            {(script.dialogue_ratio * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Beats */}
      {script.beats.map((beat: ScriptBeat) => (
        <div key={beat.beat_id} className="rounded-lg border border-white/[0.06] bg-white/[0.02] overflow-hidden">
          {/* Beat header */}
          <div className="flex items-center gap-2 border-b border-white/[0.04] px-3 py-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset ${BEAT_TYPE_STYLES[beat.type] || 'bg-white/10 text-white/50 ring-white/20'}`}>
              {beat.type}
            </span>
            <span className="text-[10px] text-white/30 font-mono">{beat.timestamp}</span>
            <span className="text-[10px] text-white/20">{beat.beat_id}</span>
          </div>

          {/* Shots */}
          <div className="divide-y divide-white/[0.03]">
            {beat.shots.map((shot: ScriptShot, si: number) => (
              <div key={si} className="flex gap-3 p-3">
                {/* Left: camera info */}
                <div className="w-20 shrink-0 space-y-1">
                  <div className="text-[10px] font-medium text-cyan-300/60">{shot.shot_type}</div>
                  <div className="text-[10px] text-white/30">{shot.camera_move}</div>
                  <div className="text-[10px] text-white/25">{shot.angle}</div>
                  {shot.close_up_target && (
                    <div className="text-[10px] text-amber-300/50">◆ {shot.close_up_target}</div>
                  )}
                </div>
                {/* Right: action + dialogue */}
                <div className="flex-1 min-w-0 space-y-1.5">
                  <p className="text-xs leading-relaxed text-white/60">{shot.action}</p>
                  {shot.dialogue && shot.dialogue.character && (
                    <div className="rounded bg-blue-500/[0.07] px-2.5 py-1.5 ring-1 ring-inset ring-blue-500/10">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[10px] font-semibold text-blue-300/80">{shot.dialogue.character}</span>
                        <span className="text-xs text-white/70">{shot.dialogue.line}</span>
                      </div>
                      {shot.dialogue.subtext && (
                        <p className="mt-0.5 text-[10px] text-white/30 italic">({shot.dialogue.subtext})</p>
                      )}
                      {shot.dialogue.delivery && (
                        <p className="mt-0.5 text-[10px] text-purple-300/40">★ {shot.dialogue.delivery}</p>
                      )}
                    </div>
                  )}
                  {/* SFX / Music */}
                  <div className="flex flex-wrap gap-2">
                    {shot.sfx && <span className="text-[10px] text-yellow-300/40">♪ {shot.sfx}</span>}
                    {shot.music && <span className="text-[10px] text-green-300/40">♫ {shot.music}</span>}
                    {shot.transition && <span className="text-[10px] text-white/25">→ {shot.transition}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Scene Summary */}
      {script.scene_summary && (
        <div className="rounded-lg bg-white/[0.03] p-3 ring-1 ring-inset ring-white/[0.06] space-y-2">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-white/30">场景摘要</h4>
          <div className="grid grid-cols-2 gap-2">
            {script.scene_summary.hook && (
              <div><span className="text-[10px] text-red-300/50">钩子</span><p className="text-xs text-white/50">{script.scene_summary.hook}</p></div>
            )}
            {script.scene_summary.core_reversal && (
              <div><span className="text-[10px] text-purple-300/50">反转</span><p className="text-xs text-white/50">{script.scene_summary.core_reversal}</p></div>
            )}
            {script.scene_summary.sweet_spot && (
              <div><span className="text-[10px] text-green-300/50">爽点</span><p className="text-xs text-white/50">{script.scene_summary.sweet_spot}</p></div>
            )}
            {script.scene_summary.cliffhanger && (
              <div><span className="text-[10px] text-yellow-300/50">悬念</span><p className="text-xs text-white/50">{script.scene_summary.cliffhanger}</p></div>
            )}
          </div>
          {script.scene_summary.spreadable_moment && (
            <div className="pt-1 border-t border-white/[0.04]">
              <span className="text-[10px] text-pink-300/50">名场面</span>
              <p className="text-xs text-white/50">{script.scene_summary.spreadable_moment}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Scene Source Text Editor ── */
function SceneSourceTextEditor({
  scene,
  getSceneSourceText,
  projectId,
  onUpdate,
}: {
  scene: Scene;
  getSceneSourceText: (scene: Scene) => string | null;
  projectId: string;
  onUpdate: (updates: Partial<Scene>) => void;
}) {
  const originalText = (() => {
    // Get original (non-edited) source text by temporarily ignoring edited_source_text
    const tempScene = { ...scene, edited_source_text: undefined };
    return getSceneSourceText(tempScene);
  })();
  const displayText = scene.edited_source_text ?? originalText ?? '';
  const [text, setText] = useState(displayText);
  const [saving, setSaving] = useState(false);
  const isModified = !!scene.edited_source_text;
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setText(scene.edited_source_text ?? originalText ?? '');
  }, [scene.id, scene.edited_source_text, originalText]);

  const saveText = useCallback(async (newText: string) => {
    setSaving(true);
    try {
      const editedValue = newText === originalText ? null : newText;
      await fetch(`${API_BASE_URL}/api/projects/${projectId}/scenes/${scene.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edited_source_text: editedValue ?? '' }),
      });
      onUpdate({ edited_source_text: editedValue });
    } finally {
      setSaving(false);
    }
  }, [projectId, scene.id, originalText, onUpdate]);

  const handleBlur = useCallback(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => saveText(text), 300);
  }, [text, saveText]);

  const handleRestore = useCallback(async () => {
    setText(originalText ?? '');
    setSaving(true);
    try {
      await fetch(`${API_BASE_URL}/api/projects/${projectId}/scenes/${scene.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edited_source_text: '' }),
      });
      onUpdate({ edited_source_text: null });
    } finally {
      setSaving(false);
    }
  }, [projectId, scene.id, originalText, onUpdate]);

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.04]">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold text-white/60">原文片段</h3>
          {isModified && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] text-amber-300/70 ring-1 ring-inset ring-amber-500/20">已修改</span>
          )}
          {saving && <span className="text-[10px] text-white/30">保存中...</span>}
        </div>
        {isModified && (
          <button
            type="button"
            onClick={handleRestore}
            className="text-[10px] text-blue-300/70 hover:text-blue-300 transition-colors"
          >
            恢复原文
          </button>
        )}
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlur}
        className="w-full min-h-[200px] resize-y bg-transparent px-4 py-3 text-xs leading-relaxed text-white/60 font-mono focus:outline-none focus:text-white/80 placeholder:text-white/20"
        placeholder="暂无原文片段"
      />
    </div>
  );
}

/* ── Scene Metadata Editor ── */
function SceneMetadataEditor({
  scene,
  projectId,
  onUpdate,
}: {
  scene: Scene;
  projectId: string;
  onUpdate: (updates: Partial<Scene>) => void;
}) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const saveField = useCallback(async (field: string, value: string | string[]) => {
    try {
      await fetch(`${API_BASE_URL}/api/projects/${projectId}/scenes/${scene.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      });
      onUpdate({ [field]: value } as Partial<Scene>);
    } catch { /* ignore */ }
    setEditingField(null);
  }, [projectId, scene.id, onUpdate]);

  const textFields: { key: keyof Scene; label: string }[] = [
    { key: 'description', label: '描述' },
    { key: 'action', label: '动作' },
    { key: 'core_event', label: '核心事件' },
    { key: 'dramatic_purpose', label: '叙事目的' },
    { key: 'cliffhanger', label: '悬念钩子' },
    { key: 'emotion_beat', label: '情绪节拍' },
  ];

  const selectFields: { key: keyof Scene; label: string; options: string[] }[] = [
    { key: 'narrative_mode', label: '叙事模式', options: ['action', 'dialogue', 'mixed'] },
    { key: 'hook_type', label: '开场钩子', options: ['悬念开场', '冲突开场', '情感开场', '动作开场', '对白开场', ''] },
    { key: 'dialogue_budget', label: '对白密度', options: ['low', 'medium', 'high'] },
  ];

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02]">
      <div className="px-4 py-2.5 border-b border-white/[0.04]">
        <h3 className="text-xs font-semibold text-white/60">场景元数据</h3>
      </div>
      <div className="p-4 grid grid-cols-1 gap-3">
        {/* Text fields */}
        {textFields.map(({ key, label }) => {
          const val = (scene[key] as string) || '';
          const isEditing = editingField === key;
          return (
            <div key={key} className="rounded-md bg-white/[0.02] p-2.5 ring-1 ring-inset ring-white/[0.06]">
              <label className="block text-[10px] font-semibold uppercase tracking-wider text-white/30 mb-1">{label}</label>
              {isEditing ? (
                <textarea
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={() => saveField(key, editValue)}
                  onKeyDown={(e) => { if (e.key === 'Escape') setEditingField(null); }}
                  className="w-full resize-none bg-transparent text-xs text-white/70 leading-relaxed focus:outline-none"
                  rows={2}
                />
              ) : (
                <p
                  onClick={() => { setEditingField(key as string); setEditValue(val); }}
                  className="cursor-pointer text-xs text-white/50 leading-relaxed hover:text-white/70 min-h-[1.5em]"
                >
                  {val || <span className="text-white/20 italic">点击编辑</span>}
                </p>
              )}
            </div>
          );
        })}

        {/* Select fields */}
        {selectFields.map(({ key, label, options }) => (
          <div key={key} className="rounded-md bg-white/[0.02] p-2.5 ring-1 ring-inset ring-white/[0.06]">
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-white/30 mb-1">{label}</label>
            <select
              value={(scene[key] as string) || ''}
              onChange={(e) => saveField(key, e.target.value)}
              className="w-full bg-transparent text-xs text-white/60 focus:outline-none cursor-pointer"
            >
              {options.map((opt) => (
                <option key={opt} value={opt} className="bg-bg-1 text-white">{opt || '（无）'}</option>
              ))}
            </select>
          </div>
        ))}

        {/* Characters present — tag style */}
        <div className="rounded-md bg-white/[0.02] p-2.5 ring-1 ring-inset ring-white/[0.06]">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-white/30 mb-1">出场角色</label>
          <div className="flex flex-wrap gap-1">
            {(scene.characters_present || []).map((c: string) => (
              <span key={c} className="rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] text-purple-300/70 ring-1 ring-inset ring-purple-500/15">{c}</span>
            ))}
            {(!scene.characters_present || scene.characters_present.length === 0) && (
              <span className="text-[10px] text-white/20 italic">无</span>
            )}
          </div>
        </div>

        {/* Tension score */}
        <div className="rounded-md bg-white/[0.02] p-2.5 ring-1 ring-inset ring-white/[0.06]">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-white/30 mb-1">
            张力分数 <span className="text-white/50">{((scene.tension_score || 0) * 100).toFixed(0)}%</span>
          </label>
          <input
            type="range"
            min="0" max="1" step="0.05"
            value={scene.tension_score || 0}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              onUpdate({ tension_score: v });
              saveField('tension_score' as keyof Scene, String(v));
            }}
            className="w-full accent-blue-400"
          />
        </div>
      </div>
    </div>
  );
}

/* ── Story Bible Panel (Accordion) ── */
/* eslint-disable @typescript-eslint/no-explicit-any */
function StoryBiblePanel({ projectId, store }: { projectId: string | undefined; store: any }) {
  const [storyBible, setStoryBible] = useState<any>(null);
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    fetch(`${API_BASE_URL}/api/projects/${projectId}/story-bible`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setStoryBible(data); })
      .catch(() => {});
  }, [projectId]);

  const toggleSection = (key: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const saveOverride = useCallback(async (key: string, value: any) => {
    if (!projectId) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/projects/${projectId}/story-bible`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ overrides: { [key]: value } }),
      });
      if (res.ok) {
        const data = await res.json();
        setStoryBible((prev: any) => prev ? { ...prev, novel_analysis: data.novel_analysis } : prev);
      }
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  if (!storyBible) return null;

  const analysis = storyBible.novel_analysis || {};
  const report = storyBible.novel_analysis_report || {};

  const sections = [
    {
      key: 'overview',
      title: '概述',
      render: () => (
        <div className="space-y-2">
          <StoryBibleField label="类型" value={analysis.genre_type || ''} onSave={(v: string) => saveOverride('genre_type', v)} />
          <StoryBibleField label="时代" value={analysis.era || ''} onSave={(v: string) => saveOverride('era', v)} />
          <StoryBibleField label="节奏" value={analysis.pacing_type || ''} onSave={(v: string) => saveOverride('pacing_type', v)} />
          <StoryBibleField label="可行性" value={analysis.feasibility_score != null ? String(analysis.feasibility_score) : ''} onSave={(v: string) => saveOverride('feasibility_score', parseFloat(v) || 0)} />
          <StoryBibleField label="目标受众" value={typeof analysis.target_audience === 'object' ? JSON.stringify(analysis.target_audience) : (analysis.target_audience || '')} onSave={(v: string) => saveOverride('target_audience', v)} />
        </div>
      ),
    },
    {
      key: 'themes',
      title: '主题与风格',
      render: () => {
        const vb = analysis.visual_baseline || {};
        return (
          <div className="space-y-2">
            <div className="rounded-md bg-white/[0.02] p-2 ring-1 ring-inset ring-white/[0.06]">
              <label className="block text-[10px] font-semibold text-white/30 mb-1">主题</label>
              <p className="text-xs text-white/50">{Array.isArray(analysis.themes) ? analysis.themes.join(', ') : '—'}</p>
            </div>
            <StoryBibleField label="艺术风格" value={vb.art_style || ''} onSave={(v: string) => saveOverride('visual_baseline', { ...vb, art_style: v })} />
            <StoryBibleField label="色彩体系" value={vb.color_system || ''} onSave={(v: string) => saveOverride('visual_baseline', { ...vb, color_system: v })} />
            <StoryBibleField label="光影基线" value={vb.lighting_baseline || ''} onSave={(v: string) => saveOverride('visual_baseline', { ...vb, lighting_baseline: v })} />
          </div>
        );
      },
    },
    {
      key: 'characters',
      title: `角色体系 (${store.characters?.length || 0})`,
      render: () => (
        <div className="space-y-2">
          {(store.characters || []).map((c: any) => (
            <div key={c.id} className="rounded-md bg-white/[0.02] p-2 ring-1 ring-inset ring-white/[0.06]">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-white/70">{c.name}</span>
                <span className={`rounded-full px-1.5 py-0.5 text-[9px] ring-1 ring-inset ${
                  c.role === 'protagonist' ? 'bg-blue-500/15 text-blue-300/70 ring-blue-500/20' :
                  c.role === 'antagonist' ? 'bg-red-500/15 text-red-300/70 ring-red-500/20' :
                  'bg-white/5 text-white/40 ring-white/10'
                }`}>{c.role}</span>
              </div>
              <p className="text-[10px] text-white/40 leading-relaxed">{c.personality || c.description || '—'}</p>
            </div>
          ))}
        </div>
      ),
    },
    {
      key: 'world',
      title: `世界构建 (${store.locations?.length || 0})`,
      render: () => (
        <div className="space-y-2">
          {(store.locations || []).map((l: any) => (
            <div key={l.id} className="rounded-md bg-white/[0.02] p-2 ring-1 ring-inset ring-white/[0.06]">
              <span className="text-xs font-medium text-white/70">{l.name}</span>
              <p className="text-[10px] text-white/40 mt-0.5">{l.description || l.visual_description || '—'}</p>
            </div>
          ))}
          {(store.locations || []).length === 0 && <p className="text-xs text-white/25">暂无场景地点</p>}
        </div>
      ),
    },
    {
      key: 'outline',
      title: `故事大纲 (${store.scenes?.length || 0} 场)`,
      render: () => (
        <div className="space-y-1">
          {(store.scenes || []).map((s: any, idx: number) => (
            <div key={s.id} className="flex items-center gap-2 rounded px-2 py-1 hover:bg-white/[0.03]">
              <span className="shrink-0 w-6 text-right text-[10px] font-mono text-white/25">{idx + 1}</span>
              <div className="flex-1 min-w-0">
                <span className="text-[10px] text-white/50 truncate block">{s.heading || s.core_event || '—'}</span>
              </div>
              <div className="shrink-0 w-8 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-red-500" style={{ width: `${(s.tension_score || 0) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      key: 'adaptation',
      title: '改编建议',
      render: () => {
        const sdp = analysis.short_drama_params || {};
        const adaptation = report.short_drama_adaptation || report.pacing_and_adaptation || '';
        return (
          <div className="space-y-2">
            {Object.entries(sdp).map(([k, v]) => (
              <StoryBibleField key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')} onSave={(val: string) => {
                try { saveOverride('short_drama_params', { ...sdp, [k]: JSON.parse(val) }); } catch { saveOverride('short_drama_params', { ...sdp, [k]: val }); }
              }} />
            ))}
            {typeof adaptation === 'string' && adaptation && (
              <div className="rounded-md bg-white/[0.02] p-2 ring-1 ring-inset ring-white/[0.06]">
                <label className="block text-[10px] font-semibold text-white/30 mb-1">AI改编分析</label>
                <p className="text-[10px] text-white/40 leading-relaxed whitespace-pre-wrap">{adaptation}</p>
              </div>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.015]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.04]">
        <h3 className="text-xs font-semibold text-white/60">Story Bible</h3>
        {saving && <span className="text-[10px] text-white/30">保存中...</span>}
      </div>
      <div className="divide-y divide-white/[0.04]">
        {sections.map((sec) => (
          <div key={sec.key}>
            <button
              type="button"
              onClick={() => toggleSection(sec.key)}
              className="flex w-full items-center gap-2 px-4 py-2.5 text-left hover:bg-white/[0.02] transition-colors"
            >
              <span className="flex-1 text-xs font-medium text-white/50">{sec.title}</span>
              <svg
                width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className={`text-white/25 transition-transform ${openSections.has(sec.key) ? 'rotate-180' : ''}`}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {openSections.has(sec.key) && (
              <div className="px-4 pb-3">
                {sec.render()}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Story Bible Inline Field ── */
function StoryBibleField({ label, value, onSave }: { label: string; value?: string; onSave: (v: string) => void }) {
  const displayValue = (value && typeof value === 'object') ? JSON.stringify(value) : (value || '');
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(displayValue);

  useEffect(() => { setVal((value && typeof value === 'object') ? JSON.stringify(value) : (value || '')); }, [value]);

  return (
    <div className="rounded-md bg-white/[0.02] p-2 ring-1 ring-inset ring-white/[0.06]">
      <label className="block text-[10px] font-semibold text-white/30 mb-0.5">{label}</label>
      {editing ? (
        <input
          autoFocus
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onBlur={() => { onSave(val); setEditing(false); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { onSave(val); setEditing(false); } if (e.key === 'Escape') setEditing(false); }}
          className="w-full bg-transparent text-xs text-white/70 focus:outline-none"
        />
      ) : (
        <p
          onClick={() => setEditing(true)}
          className="cursor-pointer text-xs text-white/50 hover:text-white/70 min-h-[1.2em]"
        >
          {displayValue || <span className="text-white/20 italic">点击编辑</span>}
        </p>
      )}
    </div>
  );
}

/* ── Script Three Column Layout with resizable panels ── */
/* eslint-disable @typescript-eslint/no-explicit-any */
function ScriptThreeColumnLayout({
  store,
  selectedScene,
  sceneReports,
  getSceneSourceText,
  middleColumnRef,
  onEnterCanvas,
  onCancel,
  onRetry,
}: {
  store: any;
  selectedScene: Scene | undefined;
  sceneReports: SceneStoryboardReadinessReport[];
  getSceneSourceText: (scene: Scene) => string | null;
  middleColumnRef: React.RefObject<HTMLDivElement | null>;
  onEnterCanvas: (sceneId: string, entryMode: 'production' | 'patch') => void;
  onCancel?: () => void;
  onRetry?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Widths as fractions of total (left, middle, right). Default: left=15%, mid=42.5%, right=42.5%
  const [colWidths, setColWidths] = useState([0.15, 0.425, 0.425]);
  const dragging = useRef<{ idx: number; startX: number; startWidths: number[] } | null>(null);

  // Script generation state
  const [scriptStreaming, setScriptStreaming] = useState(false);
  const [scriptStreamText, setScriptStreamText] = useState('');
  const [scriptUserDir, setScriptUserDir] = useState('');
  const scriptAbortRef = useRef<AbortController | null>(null);
  const scriptTextRef = useRef('');
  const [metaCollapsed, setMetaCollapsed] = useState(false);
  const sceneReportMap = useMemo(
    () => new Map(sceneReports.map((report) => [report.sceneId, report])),
    [sceneReports],
  );
  const selectedSceneReport = selectedScene ? sceneReportMap.get(selectedScene.id) : undefined;

  // Batch script generation state
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{ completed: number; total: number; current: string } | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const batchAbortRef = useRef<AbortController | null>(null);

  // Reset stream text when scene changes, show persisted script if available
  useEffect(() => {
    setScriptStreamText('');
    setScriptStreaming(false);
    scriptAbortRef.current?.abort();
    scriptAbortRef.current = null;
  }, [store.selectedSceneId]);

  const handleGenerateScript = useCallback(async () => {
    if (!selectedScene) return;

    const abortController = new AbortController();
    scriptAbortRef.current = abortController;
    setScriptStreaming(true);
    setScriptStreamText('');
    scriptTextRef.current = '';

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${selectedScene.project_id}/scenes/${selectedScene.id}/generate-script`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_direction: scriptUserDir || null }),
          signal: abortController.signal,
        },
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `API Error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.type === 'text') {
              scriptTextRef.current += payload.content;
              setScriptStreamText(scriptTextRef.current);
            } else if (payload.type === 'done') {
              // Update scene in store with generated script + JSON
              const updates: Record<string, unknown> = { generated_script: scriptTextRef.current };
              if (payload.script_json) {
                updates.generated_script_json = payload.script_json;
              }
              store.updateScene?.(selectedScene.id, updates);
            } else if (payload.type === 'error') {
              console.error('Script generation error:', payload.message);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Script generation failed:', err);
      }
    } finally {
      setScriptStreaming(false);
      scriptAbortRef.current = null;
    }
  }, [selectedScene, scriptUserDir, store]);

  const handleStopGeneration = useCallback(() => {
    scriptAbortRef.current?.abort();
    scriptAbortRef.current = null;
    setScriptStreaming(false);
  }, []);

  // ── Batch script generation ──
  const handleBatchGenerate = useCallback(async () => {
    if (!store.scenes.length) return;
    const projectId = store.scenes[0]?.project_id;
    if (!projectId) return;

    const abortController = new AbortController();
    batchAbortRef.current = abortController;
    setBatchGenerating(true);
    const alreadyDone = store.scenes.filter((s: Scene) => !!s.generated_script_json).length;
    setBatchProgress({ completed: alreadyDone, total: store.scenes.length, current: '' });

    // Persist batch state to localStorage for recovery after refresh
    try { localStorage.setItem(`batch_generating_${projectId}`, JSON.stringify({ started: Date.now(), userDirection: scriptUserDir || '' })); } catch { /* ignore */ }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/scenes/generate-all-scripts`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_direction: scriptUserDir || null, skip_completed: true }),
          signal: abortController.signal,
        },
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `API Error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.type === 'batch_start') {
              setBatchId(payload.batch_id);
              setBatchProgress({ completed: 0, total: payload.total, current: '' });
            } else if (payload.type === 'scene_start') {
              setBatchProgress(prev => prev ? { ...prev, current: payload.heading || `场景 ${payload.index + 1}` } : prev);
            } else if (payload.type === 'scene_complete') {
              setBatchProgress(prev => prev ? { ...prev, completed: prev.completed + 1, current: '' } : prev);
              // 刷新场景数据
              try {
                const scenesRes = await fetch(`${API_BASE_URL}/api/projects/${projectId}/scenes`);
                if (scenesRes.ok) {
                  const scenesData = await scenesRes.json();
                  store.setScenes(scenesData);
                }
              } catch { /* skip */ }
            } else if (payload.type === 'scene_skipped') {
              setBatchProgress(prev => prev ? { ...prev, completed: prev.completed + 1 } : prev);
            } else if (payload.type === 'scene_error') {
              setBatchProgress(prev => prev ? { ...prev, completed: prev.completed + 1, current: '' } : prev);
            } else if (payload.type === 'batch_complete') {
              // 最终刷新
              try {
                const scenesRes = await fetch(`${API_BASE_URL}/api/projects/${projectId}/scenes`);
                if (scenesRes.ok) {
                  const scenesData = await scenesRes.json();
                  store.setScenes(scenesData);
                }
              } catch { /* skip */ }
            }
          } catch { /* skip malformed JSON */ }
        }
      }
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Batch script generation failed:', err);
      }
    } finally {
      setBatchGenerating(false);
      setBatchProgress(null);
      setBatchId(null);
      batchAbortRef.current = null;
      // Clear persisted batch state
      const pid = store.scenes[0]?.project_id;
      if (pid) { try { localStorage.removeItem(`batch_generating_${pid}`); } catch { /* ignore */ } }
    }
  }, [store, scriptUserDir]);

  const handleStopBatch = useCallback(async () => {
    // 先取消 fetch 流
    batchAbortRef.current?.abort();
    batchAbortRef.current = null;
    // 通知后端取消
    if (batchId && store.scenes[0]?.project_id) {
      try {
        await fetch(
          `${API_BASE_URL}/api/projects/${store.scenes[0].project_id}/scenes/cancel-batch/${batchId}`,
          { method: 'POST' },
        );
      } catch { /* ignore */ }
    }
    setBatchGenerating(false);
    setBatchProgress(null);
    setBatchId(null);
    // Clear persisted batch state
    const pid = store.scenes[0]?.project_id;
    if (pid) { try { localStorage.removeItem(`batch_generating_${pid}`); } catch { /* ignore */ } }
  }, [batchId, store.scenes]);

  // Auto-resume batch generation after page refresh
  const batchResumeChecked = useRef(false);
  useEffect(() => {
    if (batchResumeChecked.current) return;
    batchResumeChecked.current = true;
    if (!store.scenes.length || batchGenerating) return;
    const pid = store.scenes[0]?.project_id;
    if (!pid) return;
    try {
      const saved = localStorage.getItem(`batch_generating_${pid}`);
      if (!saved) return;
      const { started } = JSON.parse(saved);
      // Only resume if started within last 30 minutes
      if (Date.now() - started > 30 * 60 * 1000) {
        localStorage.removeItem(`batch_generating_${pid}`);
        return;
      }
      // Check if there are still scenes without scripts
      const unfinished = store.scenes.filter((s: Scene) => !s.generated_script_json);
      if (unfinished.length === 0) {
        localStorage.removeItem(`batch_generating_${pid}`);
        return;
      }
      // Auto-resume
      handleBatchGenerate();
    } catch { /* ignore */ }
  }, [store.scenes, batchGenerating, handleBatchGenerate]);

  const handleMouseDown = useCallback((idx: number, e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = { idx, startX: e.clientX, startWidths: [...colWidths] };

    const handleMouseMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const totalW = containerRef.current.offsetWidth;
      const dx = (ev.clientX - dragging.current.startX) / totalW;
      const { idx: i, startWidths: sw } = dragging.current;

      const minFrac = 80 / totalW; // min 80px
      let left = sw[i] + dx;
      let right = sw[i + 1] - dx;
      if (left < minFrac) { right += left - minFrac; left = minFrac; }
      if (right < minFrac) { left += right - minFrac; right = minFrac; }

      const next = [...sw];
      next[i] = left;
      next[i + 1] = right;
      setColWidths(next);
    };

    const handleMouseUp = () => {
      dragging.current = null;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [colWidths]);

  return (
    <div className="flex h-full" ref={containerRef}>
      {/* Left Column: Scene List */}
      <div style={{ width: `${colWidths[0] * 100}%` }} className="shrink-0 flex flex-col overflow-hidden">
        {/* Sticky header: title + buttons + progress */}
        <div className="shrink-0 p-3 pb-0">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-white/50">场景列表</h3>
            <div className="flex items-center gap-1.5">
              {/* 一键生成全部剧本按钮 */}
              {store.scenes.length > 0 && !store.importing && (
                batchGenerating ? (
                  <button
                    type="button"
                    onClick={handleStopBatch}
                    className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-amber-400 ring-1 ring-amber-400/30 hover:bg-amber-400/10 transition-colors"
                  >
                    <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
                    停止
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleBatchGenerate}
                    disabled={scriptStreaming}
                    className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-blue-400 ring-1 ring-blue-400/30 hover:bg-blue-400/10 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                    title="按顺序为所有未生成剧本的场景一键生成剧本"
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5,3 19,12 5,21" />
                    </svg>
                    一键生成
                  </button>
                )
              )}
              {store.importing && store.scenes.length > 0 && (
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 animate-spin rounded-full border border-blue-400/30 border-t-blue-400" />
                {onCancel && (
                  <button
                    type="button"
                    onClick={onCancel}
                    className="text-[10px] text-red-400/70 hover:text-red-400 transition-colors"
                  >
                    停止
                  </button>
                )}
              </div>
            )}
            </div>
          </div>
          {/* 批量生成进度条 */}
          {batchGenerating && batchProgress && (
            <div className="mb-2 rounded-lg border border-blue-400/20 bg-blue-400/[0.04] p-2">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-blue-300/80">
                  {batchProgress.current ? `生成中: ${batchProgress.current}` : '准备中...'}
                </span>
                <span className="text-white/40">{batchProgress.completed}/{batchProgress.total}</span>
              </div>
              <div className="mt-1.5 h-1 w-full rounded-full bg-white/[0.06] overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-400/60 transition-all duration-500"
                  style={{ width: `${batchProgress.total > 0 ? (batchProgress.completed / batchProgress.total) * 100 : 0}%` }}
                />
              </div>
            </div>
          )}
        </div>
        {/* Scrollable scene list */}
        <div className="flex-1 overflow-y-auto px-3 pb-3 scrollbar-thin">
        <div className="space-y-1.5">
          {store.scenes.map((scene: Scene, idx: number) => (
            <button
              key={scene.id}
              id={`scene-list-${scene.id}`}
              type="button"
              onClick={() => {
                store.selectScene(scene.id);
                const el = document.getElementById(`source-scene-${scene.id}`);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
              className={`w-full rounded-lg border p-2.5 text-left transition-all ${
                store.selectedSceneId === scene.id
                  ? 'border-blue-400/60 bg-blue-400/[0.06]'
                  : 'border-white/[0.06] hover:border-white/[0.12] hover:bg-white/[0.03]'
              }`}
            >
              {(() => {
                const report = sceneReportMap.get(scene.id);
                const badgeClass =
                  report?.status === 'ready'
                    ? 'border-emerald-500/20 bg-emerald-500/[0.10] text-emerald-200/90'
                    : report?.status === 'patchable'
                      ? 'border-amber-500/20 bg-amber-500/[0.10] text-amber-200/90'
                      : 'border-rose-500/20 bg-rose-500/[0.10] text-rose-200/90';

                return report ? (
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className={`rounded-full border px-2 py-1 text-[10px] ${badgeClass}`}>
                      {report.status === 'ready' ? '可进画布' : report.status === 'patchable' ? '需补齐' : '需返修'}
                    </span>
                    <span className="text-[10px] text-white/30">
                      ready {report.readyShotIds.length} / blocked {report.blockedShotIds.length}
                    </span>
                  </div>
                ) : null;
              })()}
              <div className="flex items-start gap-2">
                <span className="shrink-0 rounded bg-blue-500/15 px-1 py-0.5 text-[10px] font-mono text-blue-300">
                  {String(idx + 1).padStart(2, '0')}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white/85">
                    {scene.location || scene.heading || '未命名场景'}
                  </p>
                  {scene.heading && (
                    <p className="mt-0.5 truncate text-xs text-green-300/60">
                      {scene.heading
                        .replace(/\bINT\b\.?/gi, '室内')
                        .replace(/\bEXT\b\.?/gi, '室外')
                        .replace(/\bFLASHBACK\b\.?/gi, '闪回')
                        .replace(/\bI\/E\b\.?/gi, '内外')
                        .replace(/\s+/g, ' ')
                        .trim()}
                    </p>
                  )}
                </div>
                {/* 剧本生成状态标识 */}
                {(scene.generated_script_json || scene.generated_script) ? (
                  <span className="shrink-0 mt-0.5" title="已生成剧本">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-green-400/70">
                      <polyline points="20,6 9,17 4,12" />
                    </svg>
                  </span>
                ) : (
                  <span className="shrink-0 mt-1 h-2 w-2 rounded-full bg-white/15" title="未生成剧本" />
                )}
              </div>
            </button>
          ))}
          {store.scenes.length === 0 && store.importing && (
            <div className="flex flex-col items-center gap-3 py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-400/30 border-t-blue-400" />
              <p className="text-center text-xs text-white/40">场景生成中...</p>
              {onCancel && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-medium text-red-400 ring-1 ring-red-400/30 hover:bg-red-400/10 transition-colors"
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
                  停止
                </button>
              )}
            </div>
          )}
          {store.scenes.length === 0 && !store.importing && (
            <div className="flex flex-col items-center gap-3 py-8">
              {store.pipelineError ? (
                <>
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-500/10 ring-1 ring-red-500/20">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-red-400">
                      <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                    </svg>
                  </div>
                  <p className="text-center text-xs text-red-300/70">场景生成失败</p>
                  <p className="max-w-48 text-center text-[10px] text-white/25 leading-relaxed">{store.pipelineError}</p>
                </>
              ) : (
                <p className="text-center text-xs text-white/30">暂无场景数据</p>
              )}
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="rounded-full px-3 py-1.5 text-[11px] font-medium text-brand ring-1 ring-brand/30 hover:bg-brand/10 transition-colors"
                >
                  重新开始
                </button>
              )}
            </div>
          )}
        </div>
        </div>
      </div>

      {/* Divider 1 */}
      <ResizeDivider onMouseDown={(e) => handleMouseDown(0, e)} />

      {/* Middle Column: Source Text / Scene Detail + Story Bible */}
      <div style={{ width: `${colWidths[1] * 100}%` }} className="shrink-0 overflow-y-auto scrollbar-thin" ref={middleColumnRef}>
        {/* Tab Bar */}
        <div className="sticky top-0 z-10 flex gap-0 border-b border-white/[0.06] bg-bg-0/95 backdrop-blur-sm">
          <button
            type="button"
            onClick={() => store.setMiddleColumnMode('all')}
            className={`px-4 py-2.5 text-xs font-medium transition-colors ${
              store.middleColumnMode === 'all'
                ? 'text-blue-300 border-b-2 border-blue-400'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            全部场景
          </button>
          <button
            type="button"
            onClick={() => store.setMiddleColumnMode('single')}
            className={`px-4 py-2.5 text-xs font-medium transition-colors ${
              store.middleColumnMode === 'single'
                ? 'text-blue-300 border-b-2 border-blue-400'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            场景详情
          </button>
        </div>

        <div className="p-4">
          {store.middleColumnMode === 'all' ? (
            /* ── 全部场景模式 ── */
            store.scenes.length > 0 ? (
              <div className="space-y-6">
                {store.scenes.map((scene: Scene, idx: number) => {
                  const sourceText = getSceneSourceText(scene);
                  return (
                    <div
                      key={scene.id}
                      id={`source-scene-${scene.id}`}
                      onClick={() => {
                        store.selectScene(scene.id);
                        store.setMiddleColumnMode('single');
                        const leftEl = document.getElementById(`scene-list-${scene.id}`);
                        if (leftEl) leftEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                      }}
                      className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                        store.selectedSceneId === scene.id
                          ? 'border-blue-400/40 bg-blue-400/[0.04]'
                          : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-white/70">
                          原文 - 场景 {String(idx + 1).padStart(2, '0')}
                        </h3>
                        {scene.edited_source_text && (
                          <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] text-amber-300/70 ring-1 ring-inset ring-amber-500/20">已修改</span>
                        )}
                      </div>
                      {sourceText ? (
                        <p className="whitespace-pre-wrap text-xs leading-relaxed text-white/50 line-clamp-6">
                          {sourceText}
                        </p>
                      ) : (
                        <div className="flex h-20 items-center justify-center rounded-lg border border-dashed border-white/10">
                          <p className="text-xs text-white/25">未找到匹配的原文片段</p>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Story Bible Panel at bottom of all-scenes mode */}
                <StoryBiblePanel projectId={store.project?.id} store={store} />
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-white/25">
                  {store.importing ? '场景生成中...' : '暂无场景数据'}
                </p>
              </div>
            )
          ) : (
            /* ── 场景详情模式 ── */
            selectedScene ? (
              <div className="space-y-6">
                {/* Source Text Editor */}
                <SceneSourceTextEditor
                  scene={selectedScene}
                  getSceneSourceText={getSceneSourceText}
                  projectId={store.project?.id || ''}
                  onUpdate={(updates) => store.updateScene(selectedScene.id, updates)}
                />

                {/* Scene Metadata Editor */}
                <SceneMetadataEditor
                  scene={selectedScene}
                  projectId={store.project?.id || ''}
                  onUpdate={(updates) => store.updateScene(selectedScene.id, updates)}
                />

                {/* Story Bible Panel */}
                <StoryBiblePanel projectId={store.project?.id} store={store} />
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center">
                <p className="text-sm text-white/30">请在左侧选择一个场景</p>
              </div>
            )
          )}
        </div>
      </div>

      {/* Divider 2 */}
      <ResizeDivider onMouseDown={(e) => handleMouseDown(1, e)} />

      {/* Right Column: Script Generation */}
      <div style={{ width: `${colWidths[2] * 100}%` }} className="shrink-0 flex flex-col overflow-hidden">
        {selectedScene ? (
          <>
            {/* Top: Collapsible Scene Metadata */}
            <div className={`shrink-0 overflow-y-auto p-4 border-b border-white/[0.06] ${metaCollapsed ? '' : 'max-h-[40%]'}`}>
              <button
                type="button"
                onClick={() => setMetaCollapsed(!metaCollapsed)}
                className="flex w-full items-center justify-between mb-2"
              >
                <h3 className="text-base font-bold text-white/95">{selectedScene.heading || selectedScene.location || '场景'}</h3>
                <svg
                  width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  className={`text-white/30 transition-transform ${metaCollapsed ? '' : 'rotate-180'}`}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {!metaCollapsed && (
                <div>
                  {selectedScene.location && <p className="text-xs text-green-300/60 mb-3">{selectedScene.location}</p>}
                  <div className="divide-y divide-white/[0.04]">
                    {selectedScene.time_of_day && <div className="flex gap-2 py-1.5"><span className="shrink-0 text-xs font-medium text-white/30 w-14">时间</span><span className="text-xs text-white/60">{selectedScene.time_of_day}</span></div>}
                    {selectedScene.description && <div className="flex gap-2 py-1.5"><span className="shrink-0 text-xs font-medium text-white/30 w-14">描述</span><span className="text-xs text-white/60 leading-relaxed">{selectedScene.description}</span></div>}
                    {selectedScene.action && <div className="flex gap-2 py-1.5"><span className="shrink-0 text-xs font-medium text-white/30 w-14">动作</span><span className="text-xs text-white/60 leading-relaxed">{selectedScene.action}</span></div>}
                    {selectedScene.dramatic_purpose && <div className="flex gap-2 py-1.5"><span className="shrink-0 text-xs font-medium text-white/30 w-14">目的</span><span className="text-xs text-white/60 leading-relaxed">{selectedScene.dramatic_purpose}</span></div>}
                    {selectedScene.core_event && <div className="flex gap-2 py-1.5"><span className="shrink-0 text-xs font-medium text-white/30 w-14">核心</span><span className="text-xs text-white/60 leading-relaxed">{selectedScene.core_event}</span></div>}
                  </div>
                  {selectedScene.characters_present && selectedScene.characters_present.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-white/25 mb-1.5">出场角色</p>
                      <div className="flex flex-wrap gap-1">
                        {selectedScene.characters_present.map((c: string) => (
                          <span key={c} className="rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] text-purple-300/70 ring-1 ring-inset ring-purple-500/15">{c}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {selectedSceneReport && (
              <div className="mx-4 rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.26em] text-cyan-300/70">
                      Storyboard Video Readiness
                    </div>
                    <div className="mt-2 text-sm text-white/75">
                      {selectedSceneReport.status === 'ready'
                        ? '当前 Scene 已通过双层硬门，可直接进入造物画布。'
                        : selectedSceneReport.status === 'patchable'
                          ? '当前 Scene 可进入补齐模式，但还不能直接跑完整视频链。'
                          : '当前 Scene 仍被硬门阻塞，需要先回到剧本阶段补分镜。'}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span
                      className={`rounded-full border px-2.5 py-1 text-[10px] ${
                        selectedSceneReport.status === 'ready'
                          ? 'border-emerald-500/20 bg-emerald-500/[0.10] text-emerald-200/90'
                          : selectedSceneReport.status === 'patchable'
                            ? 'border-amber-500/20 bg-amber-500/[0.10] text-amber-200/90'
                            : 'border-rose-500/20 bg-rose-500/[0.10] text-rose-200/90'
                      }`}
                    >
                      {selectedSceneReport.status === 'ready'
                        ? '可生产'
                        : selectedSceneReport.status === 'patchable'
                          ? '需补齐'
                          : '已阻塞'}
                    </span>
                    <span className="rounded-full bg-white/[0.05] px-2.5 py-1 text-[10px] text-white/45">
                      beat {selectedSceneReport.beatCoverage.covered}/{selectedSceneReport.beatCoverage.total || '-'}
                    </span>
                    <span className="rounded-full bg-white/[0.05] px-2.5 py-1 text-[10px] text-white/45">
                      shot {selectedSceneReport.totalShotCount}
                    </span>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedSceneReport.checklist.map((item) => (
                    <div
                      key={item.id}
                      className={`rounded-full px-2.5 py-1 text-[10px] ${
                        item.status === 'pass'
                          ? 'bg-emerald-500/10 text-emerald-200/80'
                          : item.status === 'warn'
                            ? 'bg-amber-500/10 text-amber-200/80'
                            : 'bg-rose-500/10 text-rose-200/80'
                      }`}
                    >
                      {item.label}
                    </div>
                  ))}
                </div>

                {(selectedSceneReport.blockedReasons.length > 0 || selectedSceneReport.patchableReasons.length > 0) && (
                  <div className="mt-3 space-y-2 text-xs text-white/55">
                    {selectedSceneReport.blockedReasons.map((reason) => (
                      <div key={reason} className="rounded-lg bg-rose-500/[0.08] px-3 py-2 text-rose-100/85">
                        {reason}
                      </div>
                    ))}
                    {selectedSceneReport.patchableReasons.map((reason) => (
                      <div key={reason} className="rounded-lg bg-amber-500/[0.08] px-3 py-2 text-amber-100/85">
                        {reason}
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      selectedSceneReport.status !== 'blocked' &&
                      onEnterCanvas(
                        selectedScene.id,
                        selectedSceneReport.status === 'patchable' ? 'patch' : 'production',
                      )
                    }
                    disabled={selectedSceneReport.status === 'blocked'}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                      selectedSceneReport.status === 'blocked'
                        ? 'cursor-not-allowed bg-white/[0.05] text-white/25'
                        : 'bg-cyan-500/20 text-cyan-100 hover:bg-cyan-500/30'
                    }`}
                    >
                    {selectedSceneReport.status === 'ready'
                      ? '进入造物画布'
                      : selectedSceneReport.status === 'patchable'
                        ? '进入补齐模式'
                        : '先修正分镜'}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      onEnterCanvas(
                        selectedScene.id,
                        selectedSceneReport.status === 'ready' ? 'production' : 'patch',
                      )
                    }
                    className="rounded-lg bg-white/[0.08] px-4 py-2 text-sm font-medium text-white/80 transition-colors hover:bg-white/[0.12]"
                  >
                    临时测试进入画布
                  </button>
                  {selectedSceneReport.status === 'blocked' && (
                    <div className="rounded-lg bg-white/[0.05] px-3 py-2 text-xs text-white/45">
                      先补足 beat/shot 覆盖、核心事件和场景信息，再开放画布入口。
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Middle: Script Content Area */}
            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
              {scriptStreaming ? (
                // Streaming state
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <div className="h-3 w-3 animate-spin rounded-full border border-blue-400/30 border-t-blue-400" />
                    <span className="text-xs text-blue-300/70">剧本生成中...</span>
                  </div>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed text-white/70">
                    {scriptStreamText}
                    <span className="inline-block w-0.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-text-bottom" />
                  </div>
                </div>
              ) : selectedScene.generated_script_json ? (
                // Structured JSON script (preferred)
                <StructuredScriptView script={selectedScene.generated_script_json} />
              ) : scriptStreamText ? (
                // Just finished streaming, try parse JSON
                (() => {
                  try {
                    let clean = scriptStreamText.trim();
                    if (clean.startsWith('```')) clean = clean.slice(clean.indexOf('\n') + 1);
                    if (clean.endsWith('```')) clean = clean.slice(0, -3).trim();
                    const parsed = JSON.parse(clean) as GeneratedScript;
                    if (parsed.beats) return <StructuredScriptView script={parsed} />;
                  } catch { /* fallback to text */ }
                  return (
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-white/70">
                      {scriptStreamText}
                    </div>
                  );
                })()
              ) : selectedScene.generated_script ? (
                // Persisted plain text script from DB (legacy)
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-white/70">
                  {selectedScene.generated_script}
                </div>
              ) : (
                // Empty state
                <div className="flex h-full items-center justify-center">
                  <div className="text-center">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-3 text-white/10">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                    <p className="text-sm text-white/25">点击下方按钮生成剧本</p>
                    <p className="mt-1 text-xs text-white/15">AI 将基于场景数据和小说原文创作S++级爆款短剧剧本</p>
                  </div>
                </div>
              )}
            </div>

            {/* Bottom: Input + Generate Button */}
            <div className="shrink-0 border-t border-white/[0.06] p-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={scriptUserDir}
                  onChange={(e) => setScriptUserDir(e.target.value)}
                  placeholder="添加导演指令，如：更壮烈一点..."
                  disabled={scriptStreaming}
                  className="flex-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white/80 placeholder-white/20 outline-none focus:border-blue-400/40 disabled:opacity-50"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !scriptStreaming) handleGenerateScript();
                  }}
                />
                {scriptStreaming ? (
                  <button
                    type="button"
                    onClick={handleStopGeneration}
                    className="shrink-0 rounded-lg bg-red-500/20 px-4 py-2 text-sm font-medium text-red-300 ring-1 ring-inset ring-red-500/30 hover:bg-red-500/30 transition-colors"
                  >
                    停止
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleGenerateScript}
                    className="shrink-0 rounded-lg bg-blue-500/20 px-4 py-2 text-sm font-medium text-blue-300 ring-1 ring-inset ring-blue-500/30 hover:bg-blue-500/30 transition-colors"
                  >
                    {selectedScene.generated_script || selectedScene.generated_script_json || scriptStreamText ? '重新生成' : '生成剧本'}
                  </button>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mx-auto mb-3 text-white/10">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              <p className="text-sm text-white/25">选择场景查看剧本信息</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProjectPage() {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const requestedStage = searchParams.get('stage');
  const requestedStageTab =
    requestedStage === 'info' ||
    requestedStage === 'assets' ||
    requestedStage === 'script' ||
    requestedStage === 'canvas' ||
    requestedStage === 'preview'
      ? (requestedStage as StageTab)
      : null;
  const t = useTranslations();
  const { edition } = useEdition();

  const store = useProjectStore();
  const setStageTab = useProjectStore((state) => state.setActiveStageTab);
  const hydrateProductionBoard = useBoardStore((state) => state.hydrateProductionBoard);
  const setBoardEntryContext = useBoardStore((state) => state.setBoardEntryContext);
  const selectBoardShot = useBoardStore((state) => state.selectShot);
  const boardProductionSpecs = useBoardStore((state) => state.productionSpecs);
  const boardArtifactsByShotId = useBoardStore((state) => state.artifactsByShotId);
  const boardWritebacksByShotId = useBoardStore((state) => state.writebacksByShotId);
  const hydratePreview = usePreviewStore((state) => state.hydratePreview);
  const clipDurationOverrides = usePreviewStore((state) => state.clipDurationOverrides);
  const eventSourceRef = useRef<EventSource | null>(null);
  const middleColumnRef = useRef<HTMLDivElement>(null);
  const [initialized, setInitialized] = useState(false);
  const [generatingAsset, setGeneratingAsset] = useState<string | null>(null);
  const [stageOverride, setStageOverride] = useState<StageTab | null>(requestedStageTab);
  const [canvasOverlay, setCanvasOverlay] = useState<'visible' | 'fading' | 'gone'>('idle' as any);
  const sseRetryCountRef = useRef(0);
  const sseRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sseDegradedRef = useRef(false);
  // Locked tabs based on edition
  const lockedTabs = useMemo(
    () => (edition === 'normal' ? ['preview'] : []),
    [edition],
  );
  const fallbackStageTab: StageTab = 'canvas';
  const normalizedRequestedStageTab =
    requestedStageTab && !lockedTabs.includes(requestedStageTab) ? requestedStageTab : null;
  const normalizedStoreStageTab =
    lockedTabs.includes(store.activeStageTab) ? fallbackStageTab : store.activeStageTab;
  const activeStageTab =
    stageOverride ||
    normalizedRequestedStageTab ||
    normalizedStoreStageTab;

  // ── Canvas brand animation: only plays on first entry to canvas tab ──
  const canvasAnimPlayed = useRef(false);
  const canvasOverlayTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => {
    if (activeStageTab === 'canvas') {
      // Skip animation if already played once this session
      if (canvasAnimPlayed.current) {
        setCanvasOverlay('gone');
        return;
      }
      canvasAnimPlayed.current = true;
      setCanvasOverlay('visible');
      const t1 = setTimeout(() => setCanvasOverlay('fading'), 15000);
      const t2 = setTimeout(() => setCanvasOverlay('gone'), 15800);
      canvasOverlayTimers.current = [t1, t2];
    } else {
      // Leaving canvas tab — clean up
      canvasOverlayTimers.current.forEach(clearTimeout);
      canvasOverlayTimers.current = [];
      setCanvasOverlay('idle' as any);
    }
    return () => {
      canvasOverlayTimers.current.forEach(clearTimeout);
    };
  }, [activeStageTab === 'canvas']); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!requestedStageTab) {
      return;
    }

    const nextStageTab = lockedTabs.includes(requestedStageTab)
      ? fallbackStageTab
      : requestedStageTab;

    setStageOverride(nextStageTab);
    if (store.activeStageTab !== nextStageTab) {
      setStageTab(nextStageTab);
    }
    if (typeof window !== 'undefined' && window.location.search) {
      window.history.replaceState(window.history.state, '', pathname);
    }
  }, [
    fallbackStageTab,
    lockedTabs,
    pathname,
    requestedStageTab,
    setStageTab,
    store.activeStageTab,
  ]);

  useEffect(() => {
    if (lockedTabs.includes(store.activeStageTab) && store.activeStageTab !== fallbackStageTab) {
      setStageTab(fallbackStageTab);
    }
  }, [fallbackStageTab, lockedTabs, setStageTab, store.activeStageTab]);

  useEffect(() => {
    if (!requestedStageTab && stageOverride && store.activeStageTab === stageOverride) {
      setStageOverride(null);
    }
  }, [requestedStageTab, stageOverride, store.activeStageTab]);

  // Cleanup SSE and timers on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
      if (sseRetryTimerRef.current) clearTimeout(sseRetryTimerRef.current);
      if (pollingTimerRef.current) clearInterval(pollingTimerRef.current);
    };
  }, []);

  // Load project and data
  useEffect(() => {
    // Prefetch canvas chunk in parallel with data loading so it's ready when user enters canvas tab
    import('@unrealmake/shared/components/production/ShotProductionBoard').catch(() => {});

    let cancelled = false;

    const loadProject = async () => {
      // Clear previous project's data (but preserve project itself for optimistic flow)
      store.setBeats([]);
      store.setScenes([]);
      store.setCharacters([]);
      store.setLocations([]);
      store.setShots([]);
      store.setShotGroups([]);
      store.setProps([]);
      store.setCharacterVariants([]);
      store.setNovelFullText('');
      store.setNovelAnalysis('');
      store.setNovelAnalysisStreaming(false);
      store.setAdaptationDirection(null);
      store.setScreenFormat(null);
      store.setStylePreset(null);
      store.setImporting(false); store.setAssetLibraryLocked(false);
      store.setImportTaskId(null);
      store.setImportPhase(null);
      store.setPendingSaveError(null);
      store.setPipelineError(null);

      // Check for optimistic project in sessionStorage (survives Strict Mode remount)
      let optimisticProject: Project | null = null;
      try {
        const stored = sessionStorage.getItem(`optimistic-project-${projectId}`);
        if (stored) {
          optimisticProject = JSON.parse(stored) as Project;
          store.setProject(optimisticProject);
        }
      } catch {
        // sessionStorage unavailable
      }

      // Also check if store already has this project (SPA navigation)
      if (!optimisticProject && store.project?.id === projectId) {
        optimisticProject = store.project;
      }

      if (!optimisticProject) {
        store.setLoading(true);
      }

      try {
        // Try to fetch from backend (may fail if save is still in-flight)
        let project: Project | null = null;
        const maxAttempts = optimisticProject ? 3 : 1;
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
          if (cancelled) return;
          try {
            project = await fetchAPI<Project>(`/api/projects/${projectId}`);
            if (cancelled) return;
            store.setProject(project);
            // Backend confirmed — safe to remove sessionStorage
            try { sessionStorage.removeItem(`optimistic-project-${projectId}`); } catch {}
            break;
          } catch {
            if (attempt < maxAttempts - 1) {
              await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
            }
          }
        }

        // If backend fetch failed, fall back to optimistic project
        if (!project) {
          if (optimisticProject) {
            project = optimisticProject;
            // Re-set project in store (may have been cleared by Strict Mode cleanup)
            store.setProject(optimisticProject);
          } else {
            return;
          }
        }

        if (cancelled) return;

        // Restore config from project
        if (project.adaptation_direction) {
          store.setAdaptationDirection(project.adaptation_direction as 'oscar_film' | 's_level_drama');
        }
        if (project.screen_format) {
          store.setScreenFormat(project.screen_format as 'horizontal' | 'vertical');
        }
        if (project.style_preset) {
          store.setStylePreset(project.style_preset as 'realistic' | '3d_chinese' | '2d_chinese');
        }

        // Load all asset data (catch individually so new projects don't fail)
        const [beats, scenes, characters, locations, shots, shotGroups, props, variants] = await Promise.all([
          fetchAPI<Beat[]>(`/api/projects/${projectId}/beats`).catch(() => []),
          fetchAPI<Scene[]>(`/api/projects/${projectId}/scenes`).catch(() => []),
          fetchAPI<Character[]>(`/api/projects/${projectId}/characters`).catch(() => []),
          fetchAPI<Location[]>(`/api/projects/${projectId}/locations`).catch(() => []),
          fetchAPI<Shot[]>(`/api/projects/${projectId}/shots`).catch(() => []),
          fetchAPI<ShotGroup[]>(`/api/projects/${projectId}/shot-groups`).catch(() => []),
          fetchAPI<Prop[]>(`/api/projects/${projectId}/props`).catch(() => []),
          fetchAPI<CharacterVariant[]>(`/api/projects/${projectId}/variants`).catch(() => []),
        ]);

        store.setBeats(beats);
        store.setScenes(scenes);
        store.setCharacters(characters);
        store.setLocations(locations);
        store.setShots(shots);
        store.setShotGroups(shotGroups);
        store.setProps(props);
        store.setCharacterVariants(variants);

        // Restore asset images from backend (persistent) then localStorage (fallback)
        const backendAssetIds = new Set<string>();
        try {
          const backendImages = await fetchAPI<
            { asset_id: string; slot_key: string; storage_key: string }[]
          >(`/api/projects/${projectId}/asset-images`).catch(() => []);
          for (const row of backendImages) {
            const url = `${API_BASE_URL}/uploads/${row.storage_key}`;
            store.setAssetImage(row.asset_id, row.slot_key, url);
            store.setAssetImageKey(row.asset_id, row.slot_key, row.storage_key);
            backendAssetIds.add(`${row.asset_id}:${row.slot_key}`);
          }
        } catch { /* ignore */ }
        try {
          const saved = localStorage.getItem(`assetImages_${projectId}`);
          if (saved) {
            const parsed = JSON.parse(saved);
            if (parsed && typeof parsed === 'object') {
              for (const [assetId, slots] of Object.entries(parsed)) {
                for (const [slot, val] of Object.entries(slots as Record<string, string>)) {
                  if (!backendAssetIds.has(`${assetId}:${slot}`)) {
                    store.setAssetImage(assetId, slot, val);
                  }
                }
              }
            }
          }
        } catch { /* ignore */ }

        // Load novel full text + analysis if available
        try {
          const fullTextData = await fetchAPI<{
            full_text: string | null;
            novel_analysis: string | null;
            novel_analysis_json: Record<string, unknown> | null;
          }>(
            `/api/projects/${projectId}/import/full-text`,
          );
          if (fullTextData.full_text) {
            store.setNovelFullText(fullTextData.full_text);
          }
          if (fullTextData.novel_analysis) {
            store.setNovelAnalysis(fullTextData.novel_analysis);
          }
          if (fullTextData.novel_analysis_json) {
            store.setNovelAnalysisJson(fullTextData.novel_analysis_json);
          }
        } catch {
          // No import data yet
        }

        // Check for running import task (use latest-status which doesn't need task_id)
        if (project.stage === 'import') {
          try {
            const taskInfo = await fetchAPI<{ task_id: string; status: string; current_phase: string }>(
              `/api/projects/${projectId}/import/latest-status`,
            );
            if (taskInfo && (taskInfo.status === 'running' || taskInfo.status === 'pending')) {
              store.setImporting(true);
              store.setImportTaskId(taskInfo.task_id);
              store.initPipelineStatus();
              connectSSE(taskInfo.task_id);
            }
          } catch {
            // No active import task
          }
        }
      } catch {
        // Error loading project
      } finally {
        store.setLoading(false);
        setInitialized(true);
      }
    };
    loadProject();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Reload project data after pipeline completion
  const reloadProjectData = useCallback(async () => {
    try {
      const [project, beats, scenes, characters, locations, shots, shotGroups, props, variants] = await Promise.all([
        fetchAPI<Project>(`/api/projects/${projectId}`),
        fetchAPI<Beat[]>(`/api/projects/${projectId}/beats`).catch(() => []),
        fetchAPI<Scene[]>(`/api/projects/${projectId}/scenes`).catch(() => []),
        fetchAPI<Character[]>(`/api/projects/${projectId}/characters`).catch(() => []),
        fetchAPI<Location[]>(`/api/projects/${projectId}/locations`).catch(() => []),
        fetchAPI<Shot[]>(`/api/projects/${projectId}/shots`).catch(() => []),
        fetchAPI<ShotGroup[]>(`/api/projects/${projectId}/shot-groups`).catch(() => []),
        fetchAPI<Prop[]>(`/api/projects/${projectId}/props`).catch(() => []),
        fetchAPI<CharacterVariant[]>(`/api/projects/${projectId}/variants`).catch(() => []),
      ]);
      store.setProject(project);
      store.setBeats(beats);
      store.setScenes(scenes);
      store.setCharacters(characters);
      store.setLocations(locations);
      store.setShots(shots);
      store.setShotGroups(shotGroups);
      store.setProps(props);
      store.setCharacterVariants(variants);

      // Restore asset images from backend (persistent) then localStorage (fallback)
      const backendAssetIds = new Set<string>();
      try {
        const backendImages = await fetchAPI<
          { asset_id: string; slot_key: string; storage_key: string }[]
        >(`/api/projects/${projectId}/asset-images`).catch(() => []);
        if (backendImages.length > 0) {
          for (const row of backendImages) {
            const url = `${API_BASE_URL}/uploads/${row.storage_key}`;
            store.setAssetImage(row.asset_id, row.slot_key, url);
            store.setAssetImageKey(row.asset_id, row.slot_key, row.storage_key);
            backendAssetIds.add(`${row.asset_id}:${row.slot_key}`);
          }
        }
      } catch { /* ignore backend image load errors */ }

      // Fallback: merge any localStorage images that backend doesn't have
      try {
        const saved = localStorage.getItem(`assetImages_${projectId}`);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed && typeof parsed === 'object') {
            for (const [assetId, slots] of Object.entries(parsed)) {
              for (const [slot, b64] of Object.entries(slots as Record<string, string>)) {
                if (!backendAssetIds.has(`${assetId}:${slot}`)) {
                  store.setAssetImage(assetId, slot, b64);
                }
              }
            }
          }
        }
      } catch { /* ignore parse errors */ }
    } catch {
      // ignore reload errors
    }
  }, [projectId, store]);

  // Stop polling fallback timer
  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  // Start polling fallback — checks task status when SSE is unreliable
  const startPolling = useCallback(
    (taskId: string) => {
      stopPolling();
      pollingTimerRef.current = setInterval(async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/projects/${projectId}/import/status?task_id=${taskId}`,
          );
          if (!res.ok) return;
          const info = await res.json();
          if (info.status === 'completed') {
            stopPolling();
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
            store.setImporting(false); store.setAssetLibraryLocked(false);
            store.setImportPhase(null);
            store.setImportTaskId(null);
            reloadProjectData();
          } else if (info.status === 'failed') {
            stopPolling();
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
            store.setImporting(false); store.setAssetLibraryLocked(false);
            store.setPipelineError(info.error || '场景生成失败，请重试');
            reloadProjectData();
          }
        } catch {
          // Ignore polling errors
        }
      }, 10_000); // Poll every 10 seconds
    },
    [projectId, store, reloadProjectData, stopPolling],
  );

  // Connect to SSE and handle events
  const connectSSE = useCallback(
    (taskId: string) => {
      // Clear any previous retry timer
      if (sseRetryTimerRef.current) {
        clearTimeout(sseRetryTimerRef.current);
        sseRetryTimerRef.current = null;
      }
      eventSourceRef.current?.close();

      const url = `${API_BASE_URL}/api/projects/${projectId}/import/events?task_id=${taskId}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      // Start polling fallback alongside SSE for robustness
      startPolling(taskId);

      es.onmessage = (event) => {
        try {
          const data: ImportSSEEvent = JSON.parse(event.data);
          // Reset retry state on successful message
          sseRetryCountRef.current = 0;
          sseDegradedRef.current = false;

          switch (data.type) {
            case 'phase_start':
              store.updatePipelinePhase(data.phase, { status: 'running' });
              store.setImportPhase(data.phase);
              break;

            case 'phase_done':
              store.updatePipelinePhase(data.phase, { status: 'done' });
              break;

            case 'character_found': {
              const cd = data.data;
              store.addCharacter({
                id: `tmp-char-${cd.index}`,
                project_id: projectId,
                name: cd.name,
                aliases: cd.aliases || [],
                role: cd.role as Character['role'] || 'supporting',
                description: '',
                personality: cd.personality || '',
                arc: '',
                relationships: [],
                age_range: cd.age_range,
                appearance: cd.appearance,
                costume: cd.costume,
                casting_tags: cd.casting_tags,
                desire: cd.desire,
                flaw: cd.flaw,
              });
              break;
            }

            case 'scene_found': {
              const sd = data.data;
              store.addScene({
                id: sd.scene_id || `tmp-scene-${sd.index}`,
                project_id: projectId,
                heading: sd.core_event || '',
                location: sd.location || '',
                time_of_day: '',
                description: '',
                action: '',
                dialogue: [],
                order: sd.index,
                core_event: sd.core_event,
              });
              break;
            }

            case 'location_card': {
              const ld = data.data;
              store.addLocation({
                id: `tmp-loc-${ld.index}`,
                project_id: projectId,
                name: ld.name,
                description: '',
                visual_description: '',
                mood: '',
              });
              break;
            }

            case 'prop_card': {
              const pd = data.data;
              store.addProp({
                id: `tmp-prop-${pd.index}`,
                project_id: projectId,
                name: pd.name,
                category: pd.category || '',
                description: '',
              });
              break;
            }

            case 'variant':
            case 'variant_card': {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const vd = (data as any).data;
              if (vd.variant_name) {
                store.addCharacterVariant({
                  id: `tmp-variant-${vd.index ?? Date.now()}`,
                  project_id: projectId,
                  character_id: '',
                  character_name: vd.character_name || vd.character || '',
                  variant_type: vd.variant_type || '',
                  variant_name: vd.variant_name || '',
                  tags: [],
                });
              }
              break;
            }

            case 'chapter_progress':
            case 'window_progress':
            case 'scene_progress': {
              const phase = data.phase;
              const idx = data.index + 1;
              const total = data.total;
              store.updatePipelinePhase(phase, {
                status: 'running',
                progress: { current: idx, total },
              });
              break;
            }

            case 'pipeline_complete':
              stopPolling();
              es.close();
              eventSourceRef.current = null;
              store.setImporting(false); store.setAssetLibraryLocked(false);
              store.setImportPhase(null);
              store.setImportTaskId(null);
              reloadProjectData();
              break;

            case 'error':
              stopPolling();
              es.close();
              eventSourceRef.current = null;
              store.setImporting(false); store.setAssetLibraryLocked(false);
              store.setPipelineError(data.message || '场景生成失败');
              if (data.phase) {
                store.updatePipelinePhase(data.phase, { status: 'error', detail: data.message });
              }
              // 即使出错，也加载 DB 中已保存的场景数据
              reloadProjectData();
              break;
          }
        } catch {
          // Skip malformed events
        }
      };

      es.onerror = () => {
        // Try reconnect with exponential backoff + jitter when closed/connecting
        if (es.readyState === EventSource.CLOSED || es.readyState === EventSource.CONNECTING) {
          eventSourceRef.current = null;

          // If already degraded, keep polling mode and do not spam reconnects
          if (sseDegradedRef.current) {
            return;
          }

          const retryCount = sseRetryCountRef.current;
          if (retryCount < 5) {
            const baseDelay = Math.min(2000 * Math.pow(2, retryCount), 30000);
            const jitter = Math.floor(Math.random() * 1000);
            const delay = baseDelay + jitter;
            sseRetryCountRef.current = retryCount + 1;
            sseRetryTimerRef.current = setTimeout(() => {
              // Only reconnect if we're still importing
              if (store.importing && store.importTaskId === taskId) {
                connectSSE(taskId);
              }
            }, delay);
            return;
          }

          // Exhausted retries: degrade to polling-only, probe SSE recovery later
          sseDegradedRef.current = true;
          sseRetryTimerRef.current = setTimeout(() => {
            if (store.importing && store.importTaskId === taskId) {
              sseRetryCountRef.current = 0;
              sseDegradedRef.current = false;
              connectSSE(taskId);
            }
          }, 60_000);
        }
      };
    },
    [projectId, store, reloadProjectData, startPolling, stopPolling],
  );

  // Handle file upload — client-only: read file in browser, store in zustand, no server call
  const handleFileUpload = useCallback(
    async (file: File) => {
      try {
        // Try UTF-8 first; if garbled (too many replacement chars), fall back to GBK
        const buffer = await file.arrayBuffer();
        let text = new TextDecoder('utf-8').decode(buffer);
        const replacementCount = (text.match(/\uFFFD/g) || []).length;
        if (replacementCount > text.length * 0.05) {
          // More than 5% replacement chars → likely not UTF-8, try GBK
          try {
            text = new TextDecoder('gbk').decode(buffer);
          } catch {
            // GBK decoder not available, keep UTF-8 result
          }
        }
        if (!text.trim()) return;
        store.setNovelFullText(text);
        store.setActiveStageTab('info');
      } catch {
        // read error
      }
    },
    [store],
  );

  // Handle "start scenes" from BasicInfoTab
  const handleStartScenes = useCallback(
    (taskId: string) => {
      store.setImporting(true);
      store.setAssetLibraryLocked(true);
      store.initPipelineStatus(); // also clears pipelineError
      store.setImportTaskId(taskId);
      store.setActiveStageTab('script');
      sseRetryCountRef.current = 0;
      sseDegradedRef.current = false;
      connectSSE(taskId);
    },
    [store, connectSSE],
  );

  // Handle cancel/stop pipeline
  const handleCancel = useCallback(async () => {
    const taskId = store.importTaskId;
    if (!taskId) return;

    try {
      await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/import/cancel?task_id=${taskId}`,
        { method: 'POST' },
      );
    } catch {
      // ignore network errors
    }

    // Close SSE, stop polling, and reset state
    stopPolling();
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    store.setImporting(false); store.setAssetLibraryLocked(false);
    store.setImportPhase(null);

    // Load whatever data was already saved
    reloadProjectData();
  }, [projectId, store, reloadProjectData, stopPolling]);

  // Handle retry — cancel old task + re-submit scenes extraction
  const handleRetry = useCallback(async () => {
    // Cancel existing task if any
    const oldTaskId = store.importTaskId;
    if (oldTaskId) {
      try {
        await fetch(
          `${API_BASE_URL}/api/projects/${projectId}/import/cancel?task_id=${oldTaskId}`,
          { method: 'POST' },
        );
      } catch { /* ignore */ }
      stopPolling();
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    }

    // Reset state — clear old scenes/characters so UI shows fresh loading
    store.initPipelineStatus(); // also clears pipelineError
    store.setScenes([]);
    store.setImporting(true);

    try {
      // First try the /import/retry endpoint (works if task is failed)
      if (oldTaskId) {
        const retryResp = await fetch(
          `${API_BASE_URL}/api/projects/${projectId}/import/retry?task_id=${oldTaskId}`,
          { method: 'POST' },
        );
        if (retryResp.ok) {
          connectSSE(oldTaskId);
          return;
        }
      }

      // Fallback: re-submit via start-scenes (creates new task)
      // Send novelFullText if available; backend will fall back to DB if empty
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/analysis/start-scenes`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ novel_text: store.novelFullText || '' }),
        },
      );
      if (!response.ok) {
        store.setImporting(false); store.setAssetLibraryLocked(false);
        return;
      }
      const result = await response.json();
      store.setImportTaskId(result.task_id);
      connectSSE(result.task_id);
    } catch {
      store.setImporting(false); store.setAssetLibraryLocked(false);
    }
  }, [projectId, store, connectSSE]);

  // Get source text for a scene from novelFullText (prioritizes edited_source_text)
  const getSceneSourceText = useCallback(
    (scene: Scene) => {
      if (scene.edited_source_text) return scene.edited_source_text;
      if (!store.novelFullText || !scene.source_text_start || !scene.source_text_end) return null;
      const startIdx = store.novelFullText.indexOf(scene.source_text_start);
      if (startIdx === -1) return null;
      const endIdx = store.novelFullText.indexOf(scene.source_text_end, startIdx);
      if (endIdx === -1) return store.novelFullText.slice(startIdx, startIdx + 2000);
      return store.novelFullText.slice(startIdx, endIdx + scene.source_text_end.length);
    },
    [store.novelFullText],
  );

  // Asset on-demand generation handler
  const handleAssetGenerate = useCallback(
    async (type: 'character' | 'location' | 'prop' | 'variant', mode: 'overwrite' | 'enhance') => {
      const typeMap: Record<string, string> = {
        character: 'characters',
        location: 'locations',
        prop: 'props',
        variant: 'variants',
      };
      setGeneratingAsset(type);

      try {
        const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/assets/generate/${typeMap[type]}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          console.error('Asset generation failed:', err);
          setGeneratingAsset(null);
          return;
        }

        // Poll: reload data + check backend status every 5s
        const pollInterval = setInterval(async () => {
          try {
            // Reload data so new cards appear incrementally
            await reloadProjectData();

            // Check backend generation status
            const statusResp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/assets/generate/status`);
            if (statusResp.ok) {
              const statuses = await statusResp.json();
              const taskStatus = statuses[type];
              if (taskStatus && (taskStatus.status === 'done' || taskStatus.status === 'error' || taskStatus.status === 'idle')) {
                clearInterval(pollInterval);
                setGeneratingAsset(null);
              }
            }
          } catch { /* ignore */ }
        }, 5000);

        // Safety: auto-stop after 10 min
        setTimeout(() => {
          clearInterval(pollInterval);
          setGeneratingAsset(null);
        }, 600000);
      } catch (e) {
        console.error('Asset generation request failed:', e);
        setGeneratingAsset(null);
      }
    },
    [projectId, reloadProjectData],
  );

  const productionProjection = useMemo(
    () =>
      buildShotProductionProjection({
        project: store.project,
        scenes: store.scenes,
        shots: store.shots,
        characters: store.characters,
        locations: store.locations,
        props: store.props,
        assetImages: store.assetImages,
        assetImageKeys: store.assetImageKeys,
        stylePreset: store.stylePreset,
      }),
    [
      store.project,
      store.scenes,
      store.shots,
      store.characters,
      store.locations,
      store.props,
      store.assetImages,
      store.assetImageKeys,
      store.stylePreset,
    ],
  );

  useEffect(() => {
    hydrateProductionBoard(
      projectId,
      productionProjection.sceneReports,
      productionProjection.specs,
      productionProjection.modules,
    );
  }, [
    hydrateProductionBoard,
    productionProjection.modules,
    productionProjection.sceneReports,
    productionProjection.specs,
    projectId,
  ]);

  useEffect(() => {
    const clips = buildAnimaticClips(
      boardProductionSpecs,
      boardArtifactsByShotId,
      boardWritebacksByShotId,
      clipDurationOverrides,
    );
    const sequenceBundle = buildSequenceBundle(
      projectId,
      boardProductionSpecs,
      boardArtifactsByShotId,
      boardWritebacksByShotId,
      clips,
    );

    hydratePreview(projectId, clips, sequenceBundle ? [sequenceBundle] : []);
  }, [
    boardArtifactsByShotId,
    boardProductionSpecs,
    boardWritebacksByShotId,
    clipDurationOverrides,
    hydratePreview,
    projectId,
  ]);

  const handleOpenPreview = useCallback(() => {
    store.setActiveStageTab('preview');
  }, [store]);

  const handleEnterCanvasForScene = useCallback(
    (sceneId: string, entryMode: 'production' | 'patch') => {
      setBoardEntryContext(sceneId, entryMode);
      const firstShot =
        productionProjection.specs.find(
          (spec) => spec.sceneId === sceneId && spec.storyboardStatus !== 'blocked',
        ) || productionProjection.specs.find((spec) => spec.sceneId === sceneId);

      if (firstShot) {
        selectBoardShot(firstShot.shotId);
      }
      store.setActiveStageTab('canvas');
    },
    [productionProjection.specs, selectBoardShot, setBoardEntryContext, store],
  );

  const handleJumpBackToShot = useCallback(
    (shotId: string) => {
      selectBoardShot(shotId);
      store.setActiveStageTab('canvas');
    },
    [selectBoardShot, store],
  );

  // Asset counts (scenes hidden from asset library)
  const counts = {
    all: store.characters.length + store.locations.length + store.props.length + store.characterVariants.length,
    character: store.characters.length,
    location: store.locations.length,
    prop: store.props.length,
    variant: store.characterVariants.length,
  };

  // Pipeline error
  const pipelineError = Object.values(store.pipelineStatus).find((s) => s.status === 'error');

  // Selected scene for script tab
  const selectedScene = store.scenes.find(s => s.id === store.selectedSceneId);

  if (!initialized || store.loading) {
    return (
      <div className="flex h-screen flex-col bg-bg-0">
        {/* Skeleton header bar */}
        <div className="flex h-12 shrink-0 items-center border-b border-white/[0.06] px-4">
          <div className="h-4 w-32 rounded bg-white/[0.06]" />
          <div className="ml-auto flex gap-2">
            <div className="h-6 w-16 rounded bg-white/[0.06]" />
            <div className="h-6 w-16 rounded bg-white/[0.06]" />
          </div>
        </div>
        {/* Skeleton stage tabs */}
        <div className="flex h-10 shrink-0 items-center gap-4 border-b border-white/[0.06] px-4">
          {[1,2,3,4,5].map(i => (
            <div key={i} className="h-3 w-12 rounded bg-white/[0.06]" />
          ))}
        </div>
        {/* Body area with canvas skeleton */}
        <div className="flex-1 overflow-hidden">
          <CanvasSkeleton />
        </div>
      </div>
    );
  }

  if (!store.project) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0">
        <div className="text-center">
          <p className="text-error">{t('project.loadFailed')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-bg-0">
      {/* ── Top Header ─────────────────────────────────────────── */}
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-white/[0.06] px-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push('/')}
            className="text-white/40 transition-colors hover:text-white/80"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <span className="text-sm font-semibold text-brand">虚幻造物</span>
          <span className="text-white/20">|</span>
          <span className="text-sm text-white/60">{store.project.name}</span>
        </div>

        <StageTabs
          activeTab={activeStageTab}
          onTabChange={(tab) => store.setActiveStageTab(tab as StageTab)}
          lockedTabs={lockedTabs}
        />

        <div className="flex items-center gap-2">
          <LanguageSwitcher />
        </div>
      </header>

      {/* ── Main Body ──────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - only show for assets tab */}
        {activeStageTab === 'assets' && (
          <aside className="w-36 shrink-0 border-r border-white/[0.06]">
            <AssetLibrarySidebar
              activeFilter={store.assetFilter}
              onFilterChange={(f) => store.setAssetFilter(f)}
              counts={counts}
              importing={store.importing}
              pipelineStatus={store.pipelineStatus}
              importPhase={store.importPhase}
              locked={store.assetLibraryLocked}
              onGenerate={handleAssetGenerate}
              generating={generatingAsset}
            />
          </aside>
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-hidden">
          {/* ── Info Tab ── */}
          {activeStageTab === 'info' ? (
            <BasicInfoTab
              projectId={projectId}
              onStartScenes={handleStartScenes}
              onFileUpload={handleFileUpload}
            />

          /* ── Assets Tab ── */
          ) : activeStageTab === 'assets' ? (
            <AssetLibraryGrid
              characters={store.characters}
              scenes={store.scenes}
              locations={store.locations}
              props={store.props}
              characterVariants={store.characterVariants}
              assetFilter={store.assetFilter}
              importing={store.importing}
              locked={store.assetLibraryLocked}
              projectId={projectId}
              onFileUpload={handleFileUpload}
              uploadDisabled={store.importing}
              uploadLabel={t('import.dropHint')}
              uploadHint={t('import.formatHint')}
            />

          /* ── Script Tab — Three Column Layout with resizable dividers ── */
          ) : activeStageTab === 'script' ? (
            <ScriptThreeColumnLayout
              store={store}
              selectedScene={selectedScene}
              sceneReports={productionProjection.sceneReports}
              getSceneSourceText={getSceneSourceText}
              middleColumnRef={middleColumnRef}
              onEnterCanvas={handleEnterCanvasForScene}
              onCancel={store.importing ? handleCancel : undefined}
              onRetry={handleRetry}
            />
          ) : activeStageTab === 'canvas' ? (
            <div className="relative h-full w-full">
              {/* Canvas loads in the background */}
              <ShotProductionBoard
                projectName={store.project.name}
                onOpenPreview={handleOpenPreview}
              />
              {/* Brand animation overlay — managed by page state, independent of dynamic import */}
              {(canvasOverlay === 'visible' || canvasOverlay === 'fading') && (
                <div
                  className="absolute inset-0 z-[9998] pointer-events-none"
                  style={{
                    opacity: canvasOverlay === 'fading' ? 0 : 1,
                    transition: 'opacity 800ms ease-out',
                  }}
                >
                  <ParticleBrandAnimation />
                </div>
              )}
            </div>
          ) : activeStageTab === 'preview' ? (
            <PreviewAnimaticWorkspace
              projectName={store.project.name}
              onJumpBackToShot={handleJumpBackToShot}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-white/30">
              {t('project.aiPlaceholder')}
            </div>
          )}
        </main>
      </div>

      {/* ── Bottom Status Bar ──────────────────────────────────── */}
      {store.importing && (
        <footer className="flex h-8 shrink-0 items-center border-t border-white/[0.06] px-4 text-xs text-white/40">
          <PipelineStatusBar
            pipelineStatus={store.pipelineStatus}
            importPhase={store.importPhase}
            characterCount={store.characters.length}
            sceneCount={store.scenes.length}
            locationCount={store.locations.length}
            propCount={store.props.length}
            error={pipelineError?.detail}
            onRetry={pipelineError ? handleRetry : undefined}
            onCancel={handleCancel}
          />
        </footer>
      )}

      {/* Edition badge - removed: was overlapping canvas controls */}

      {/* Pending save error toast */}
      {store.pendingSaveError && (
        <div className="fixed bottom-12 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-red-900/90 px-4 py-2 text-xs text-red-200 shadow-lg backdrop-blur">
          {store.pendingSaveError}
          <button
            type="button"
            onClick={() => store.setPendingSaveError(null)}
            className="ml-2 text-red-300 hover:text-white"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
