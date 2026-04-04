'use client';

import { useCallback, useRef, useState } from 'react';
import { useProjectStore } from '../../stores/projectStore';
import { API_BASE_URL } from '../../lib/api';

interface BasicInfoTabProps {
  projectId: string;
  onStartScenes: (taskId: string) => void;
  onFileUpload: (file: File) => void;
  uploading?: boolean;
}

/** Fire-and-forget config save — errors are silently ignored */
function saveConfig(projectId: string, patch: Record<string, string>) {
  fetch(`${API_BASE_URL}/api/projects/${projectId}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  }).catch(() => {});
}

const DIRECTION_OPTIONS = [
  { value: 'oscar_film' as const, label: '奥斯卡级院线电影' },
  { value: 's_level_drama' as const, label: 'S级百集爆款短剧' },
];

const FORMAT_OPTIONS = [
  { value: 'horizontal' as const, label: '横屏' },
  { value: 'vertical' as const, label: '竖屏' },
];

const STYLE_OPTIONS = [
  { value: 'realistic' as const, label: '仿真人' },
  { value: '3d_chinese' as const, label: '3D国漫' },
  { value: '2d_chinese' as const, label: '2D国漫' },
];

const REPORT_SECTIONS = [
  { key: 'ip_value', title: 'IP核心价值评估' },
  { key: 'character_system', title: '人物体系分析' },
  { key: 'world_and_scenes', title: '场景与世界观' },
  { key: 'pacing_and_adaptation', title: '叙事节奏与改编策略' },
  { key: 'market_positioning', title: '市场定位与受众' },
  { key: 'risk_assessment', title: '风险评估与建议' },
] as const;

export function BasicInfoTab({ projectId, onStartScenes, onFileUpload, uploading }: BasicInfoTabProps) {
  const store = useProjectStore();
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [scenesError, setScenesError] = useState<string | null>(null);
  const [scenesLoading, setScenesLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [novelCollapsed, setNovelCollapsed] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const hasNovel = store.novelFullText.length > 0;
  const configReady = store.adaptationDirection && store.screenFormat && store.stylePreset;
  const analysisComplete = store.novelAnalysis.length > 0 && !store.novelAnalysisStreaming;
  const canStartScenes = analysisComplete && configReady;

  const handleStopAnalysis = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    store.setNovelAnalysisStreaming(false);
  }, [store]);

  const handleStartAnalysis = useCallback(async () => {
    if (!store.adaptationDirection) return;
    setAnalysisError(null);
    store.setNovelAnalysis('');
    store.setNovelAnalysisJson(null);
    store.setNovelAnalysisStreaming(true);

    // Abort controller for stop button
    const controller = new AbortController();
    abortRef.current = controller;

    // Local accumulator to avoid stale closure
    let accumulated = '';

    try {
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analysis/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          adaptation_direction: store.adaptationDirection,
          novel_text: store.novelFullText,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Analysis failed' }));
        throw new Error(err.detail);
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
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') {
              accumulated += data.content;
              store.appendNovelAnalysis(data.content);
            } else if (data.type === 'done') {
              // Receive structured data from backend
              if (data.structured) {
                store.setNovelAnalysisJson(data.structured);
              }
              // Parse the accumulated JSON text to extract report sections
              const cleaned = accumulated.trim().replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?\s*```$/, '');
              try {
                const parsed = JSON.parse(cleaned);
                if (parsed && typeof parsed === 'object' && parsed.report) {
                  const parts: string[] = [];
                  for (const { key, title } of REPORT_SECTIONS) {
                    const content = parsed.report[key];
                    if (content) parts.push(`## ${title}\n\n${content}`);
                  }
                  if (parts.length > 0) {
                    store.setNovelAnalysis(parts.join('\n\n'));
                  }
                }
              } catch {
                // Keep raw text as-is (backward compat)
              }
            } else if (data.type === 'error') {
              setAnalysisError(data.message);
            }
          } catch {
            // skip malformed
          }
        }
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        // User clicked stop — not an error
      } else {
        setAnalysisError(e instanceof Error ? e.message : 'Unknown error');
      }
    } finally {
      abortRef.current = null;
      store.setNovelAnalysisStreaming(false);
    }
  }, [projectId, store]);

  const handleStartScenes = useCallback(async () => {
    setScenesError(null);
    setScenesLoading(true);
    try {
      // Send empty novel_text — backend reads full text from DB (saved during analysis)
      // This avoids browser serialization failure on large novel texts
      const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/analysis/start-scenes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ novel_text: '' }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Failed' }));
        throw new Error(err.detail);
      }
      const result = await response.json();
      onStartScenes(result.task_id);
    } catch (e) {
      setScenesError(e instanceof Error ? e.message : '启动剧本构思失败，请重试');
    } finally {
      setScenesLoading(false);
    }
  }, [projectId, onStartScenes]);

  const wordCount = hasNovel ? store.novelFullText.length : 0;

  return (
    <div className="h-full overflow-y-auto p-6 scrollbar-thin">
      <div className="mx-auto max-w-3xl space-y-6">

        {/* ── Step 1: Upload Novel (未上传时显示) ── */}
        {!hasNovel && (
          <section>
            <h3 className="mb-4 text-sm font-semibold text-white/70">Step 1 — 上传小说</h3>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const file = e.dataTransfer.files?.[0];
                if (file) onFileUpload(file);
              }}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-all ${
                dragOver
                  ? 'border-brand/60 bg-brand/5'
                  : 'border-white/10 hover:border-white/20'
              }`}
            >
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 text-white/20">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <p className="mb-2 text-sm font-medium text-white/50">
                {uploading ? '上传中...' : '拖拽小说文件到这里，或点击选择'}
              </p>
              <p className="mb-4 text-xs text-white/30">支持 .txt .md .docx .epub .pdf 格式</p>
              <button
                type="button"
                disabled={uploading}
                onClick={() => fileInputRef.current?.click()}
                className={`rounded-full px-6 py-2 text-sm font-medium transition-all ${
                  uploading
                    ? 'cursor-not-allowed bg-white/5 text-white/20'
                    : 'bg-brand text-white hover:bg-brand/80 shadow-sm shadow-brand/20'
                }`}
              >
                {uploading ? '上传中...' : '选择文件'}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.docx,.epub,.pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onFileUpload(file);
                  e.target.value = '';
                }}
              />
            </div>
          </section>
        )}

        {/* ── AI 分析报告 (最重要，放最上方) ── */}
        {(store.novelAnalysis || store.novelAnalysisStreaming) && (
          <section>
            <h3 className="mb-3 text-sm font-semibold text-white/70">
              {hasNovel ? 'Step 3 — AI 分析报告' : 'AI 分析报告'}
              {store.novelAnalysisStreaming && (
                <span className="ml-2 text-xs font-normal text-brand/70">GPT-5.4 生成中</span>
              )}
            </h3>

            {/* Director Baseline Summary (structured data) */}
            {store.novelAnalysisJson && !store.novelAnalysisStreaming && (() => {
              const nj = store.novelAnalysisJson as Record<string, unknown>;
              const ep = nj.episode_suggestion as Record<string, unknown> | undefined;
              const themes = nj.themes as string[] | undefined;
              return (
                <div className="mb-3 rounded-lg border border-brand/20 bg-brand/5 p-4">
                  <h4 className="mb-2 text-xs font-semibold text-brand/80">导演基准决策卡</h4>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    {nj.genre_type ? (
                      <div><span className="text-white/30">题材：</span><span className="text-white/60">{String(nj.genre_type)}</span></div>
                    ) : null}
                    {nj.era ? (
                      <div><span className="text-white/30">时代：</span><span className="text-white/60">{String(nj.era)}</span></div>
                    ) : null}
                    {nj.pacing_type ? (
                      <div><span className="text-white/30">节奏：</span><span className="text-white/60">{String(nj.pacing_type)}</span></div>
                    ) : null}
                    {nj.feasibility_score ? (
                      <div><span className="text-white/30">可行性：</span><span className="text-white/60">{String(nj.feasibility_score)}/10</span></div>
                    ) : null}
                    {themes && themes.length > 0 ? (
                      <div className="col-span-2"><span className="text-white/30">主题：</span><span className="text-white/60">{themes.join('、')}</span></div>
                    ) : null}
                    {ep?.count ? (
                      <div className="col-span-2">
                        <span className="text-white/30">集数建议：</span>
                        <span className="text-white/60">
                          {String(ep.count)} 集
                          {ep.duration_minutes ? (<> x {String(ep.duration_minutes)} 分钟</>) : null}
                        </span>
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })()}

            {/* Report Sections (collapsible) */}
            {!store.novelAnalysisStreaming && store.novelAnalysis ? (
              <div className="space-y-2" style={{ maxHeight: '45vh', overflowY: 'auto' }}>
                {store.novelAnalysis.split(/\n(?=## )/).map((section, idx) => {
                  const titleMatch = section.match(/^##\s*(.+)/);
                  const title = titleMatch ? titleMatch[1] : `Section ${idx + 1}`;
                  const body = titleMatch ? section.slice(titleMatch[0].length).trim() : section.trim();
                  if (!body) return null;
                  const isCollapsed = collapsedSections[title] ?? (idx > 0);
                  return (
                    <div key={idx} className="rounded-lg border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setCollapsedSections(prev => ({ ...prev, [title]: !isCollapsed }))}
                        className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-white/[0.04] transition-colors"
                      >
                        <span className="text-xs font-medium text-white/60">{title}</span>
                        <svg
                          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                          className={`text-white/20 transition-transform ${isCollapsed ? '' : 'rotate-180'}`}
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </button>
                      {!isCollapsed && (
                        <div className="border-t border-white/[0.04] px-4 py-3">
                          <p className="whitespace-pre-wrap text-xs leading-relaxed text-white/50">{body}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : store.novelAnalysisStreaming ? (
              <div>
                <div style={{ maxHeight: '45vh' }} className="overflow-y-auto rounded-lg border border-white/[0.06] bg-white/[0.02] p-5 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                  <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap text-sm leading-relaxed text-white/60">
                    {store.novelAnalysis}
                    <span className="inline-block w-2 h-4 ml-0.5 bg-brand animate-pulse rounded-sm" />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleStopAnalysis}
                  className="mt-2 flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium text-red-400 ring-1 ring-red-400/30 hover:bg-red-400/10 transition-colors"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
                  停止分析
                </button>
              </div>
            ) : null}

            {analysisError && (
              <div className="mt-2 flex items-center gap-3">
                <p className="text-xs text-red-400">{analysisError}</p>
                <button
                  type="button"
                  onClick={handleStartAnalysis}
                  className="shrink-0 rounded-full px-3 py-1 text-xs font-medium text-brand ring-1 ring-brand/30 hover:bg-brand/10 transition-colors"
                >
                  重试
                </button>
              </div>
            )}
          </section>
        )}

        {/* ── Step 4: Start Script ── */}
        {hasNovel && (
          <section>
            <button
              type="button"
              disabled={!canStartScenes || scenesLoading}
              onClick={handleStartScenes}
              className={`w-full rounded-lg py-3 text-sm font-semibold transition-all ${
                canStartScenes && !scenesLoading
                  ? 'bg-brand text-white hover:bg-brand/80 shadow-lg shadow-brand/20'
                  : 'cursor-not-allowed bg-white/5 text-white/20'
              }`}
            >
              {scenesLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="60" strokeLinecap="round" className="opacity-30" />
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                  正在启动剧本构思...
                </span>
              ) : '开始剧本构思'}
            </button>
            {scenesError && (
              <p className="mt-2 text-center text-xs text-red-400">{scenesError}</p>
            )}
            {!analysisComplete && configReady && (
              <p className="mt-2 text-center text-xs text-white/30">请先完成 AI 分析</p>
            )}
            {!configReady && (
              <p className="mt-2 text-center text-xs text-white/30">请先选择全部配置项</p>
            )}
          </section>
        )}

        {/* ── Step 2: Configuration ── */}
        <section>
          <h3 className="mb-4 text-sm font-semibold text-white/70">
            {hasNovel ? 'Step 2 — 项目配置' : '项目配置'}
          </h3>
          <div className="space-y-4">
            {/* Adaptation Direction */}
            <div>
              <label className="mb-2 block text-xs font-medium text-white/40">改编方向</label>
              <div className="flex gap-2">
                {DIRECTION_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => { store.setAdaptationDirection(opt.value); saveConfig(projectId, { adaptation_direction: opt.value }); }}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ring-1 ${
                      store.adaptationDirection === opt.value
                        ? 'bg-brand text-white ring-brand/50'
                        : 'text-white/50 ring-white/10 hover:bg-white/5 hover:text-white/70'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Screen Format */}
            <div>
              <label className="mb-2 block text-xs font-medium text-white/40">屏幕规格</label>
              <div className="flex gap-2">
                {FORMAT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => { store.setScreenFormat(opt.value); saveConfig(projectId, { screen_format: opt.value }); }}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ring-1 ${
                      store.screenFormat === opt.value
                        ? 'bg-brand text-white ring-brand/50'
                        : 'text-white/50 ring-white/10 hover:bg-white/5 hover:text-white/70'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Style Preset */}
            <div>
              <label className="mb-2 block text-xs font-medium text-white/40">风格预选</label>
              <div className="flex gap-2">
                {STYLE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => { store.setStylePreset(opt.value); saveConfig(projectId, { style_preset: opt.value }); }}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ring-1 ${
                      store.stylePreset === opt.value
                        ? 'bg-brand text-white ring-brand/50'
                        : 'text-white/50 ring-white/10 hover:bg-white/5 hover:text-white/70'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Start Analysis Button */}
            {configReady && hasNovel && (
              <button
                type="button"
                disabled={store.novelAnalysisStreaming}
                onClick={handleStartAnalysis}
                className={`mt-2 flex items-center gap-2 rounded-full px-6 py-2 text-sm font-semibold transition-all ${
                  store.novelAnalysisStreaming
                    ? 'cursor-not-allowed bg-white/10 text-white/30'
                    : 'bg-brand text-white hover:bg-brand/80 shadow-sm shadow-brand/20'
                }`}
              >
                {store.novelAnalysisStreaming ? (
                  <>
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="60" strokeLinecap="round" className="opacity-30" />
                      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                    GPT-5.4 分析中...
                  </>
                ) : (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                    {store.novelAnalysis ? '重新分析（GPT-5.4）' : '开始分析（GPT-5.4）'}
                  </>
                )}
              </button>
            )}
            {configReady && hasNovel && !store.novelAnalysisStreaming && !store.novelAnalysis && (
              <p className="text-[11px] text-white/25">
                将使用 openclaudecode.cn 的 GPT-5.4 模型，对小说全文进行影视改编可行性分析
              </p>
            )}
          </div>
        </section>

        {/* ── 小说已上传 (次要信息，放最下方) ── */}
        {hasNovel && (
          <section className="pb-12">
            <button
              type="button"
              onClick={() => setNovelCollapsed(!novelCollapsed)}
              className="flex w-full items-center justify-between rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-left transition-colors hover:bg-white/[0.04]"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-500/10">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-400">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-white/80">小说已上传</p>
                  <p className="text-[11px] text-white/35">{wordCount.toLocaleString()} 字</p>
                </div>
              </div>
              <svg
                width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className={`text-white/30 transition-transform ${novelCollapsed ? '' : 'rotate-180'}`}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {!novelCollapsed && (
              <div className="mt-2 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
                <div className="max-h-80 overflow-y-auto scrollbar-thin">
                  <p className="whitespace-pre-wrap text-xs leading-relaxed text-white/40">
                    {store.novelFullText.slice(0, 10000)}
                    {store.novelFullText.length > 10000 && (
                      <span className="text-white/20">... (共 {wordCount.toLocaleString()} 字，此处仅预览前 10,000 字)</span>
                    )}
                  </p>
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
