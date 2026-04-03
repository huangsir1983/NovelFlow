'use client';

import { memo, useCallback, useState } from 'react';
import { useCanvasStore } from '../../../stores/canvasStore';

function PromptBarInner() {
  const promptBarExpanded = useCanvasStore((s) => s.promptBarExpanded);
  const togglePromptBar = useCanvasStore((s) => s.togglePromptBar);
  const promptBarContent = useCanvasStore((s) => s.promptBarContent);
  const setPromptBarContent = useCanvasStore((s) => s.setPromptBarContent);
  const promptBarMode = useCanvasStore((s) => s.promptBarMode);
  const setPromptBarMode = useCanvasStore((s) => s.setPromptBarMode);
  const inspectedNodeId = useCanvasStore((s) => s.inspectedNodeId);

  const handleSubmit = useCallback(() => {
    if (!promptBarContent.trim()) return;
    // TODO: dispatch AI command or prompt edit based on mode
    console.log(`[PromptBar] mode=${promptBarMode}, target=${inspectedNodeId}, content=${promptBarContent}`);
    setPromptBarContent('');
  }, [promptBarContent, promptBarMode, inspectedNodeId, setPromptBarContent]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <div
      className={`
        pointer-events-auto absolute right-3 bottom-3 left-[210px] z-30
        rounded-xl border border-white/[0.08] bg-[#0a0f1a]/95 backdrop-blur-xl
        transition-all duration-300
        ${promptBarExpanded ? 'max-h-[200px]' : 'max-h-[48px]'}
      `}
    >
      {/* Collapsed bar */}
      {!promptBarExpanded && (
        <button
          onClick={togglePromptBar}
          className="flex h-[48px] w-full items-center gap-3 px-4 text-left"
        >
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-cyan-500/15">
            <span className="text-[10px] text-cyan-300">⌘</span>
          </div>
          <span className="text-[11px] text-white/35 flex-1 truncate">
            {promptBarContent || '输入 AI 指令或编辑 Prompt...'}
          </span>
          <span className="text-[10px] text-white/20">展开</span>
        </button>
      )}

      {/* Expanded bar */}
      {promptBarExpanded && (
        <div className="p-3">
          {/* Mode tabs */}
          <div className="flex items-center gap-1 mb-2">
            <button
              onClick={() => setPromptBarMode('ai')}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                promptBarMode === 'ai'
                  ? 'bg-cyan-500/20 text-cyan-300'
                  : 'bg-white/5 text-white/40 hover:text-white/60'
              }`}
            >
              AI 指令
            </button>
            <button
              onClick={() => setPromptBarMode('edit')}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition-colors ${
                promptBarMode === 'edit'
                  ? 'bg-green-500/20 text-green-300'
                  : 'bg-white/5 text-white/40 hover:text-white/60'
              }`}
            >
              Prompt 编辑
            </button>

            {inspectedNodeId && (
              <span className="ml-2 text-[9px] text-white/25 truncate">
                目标: {inspectedNodeId}
              </span>
            )}

            <button
              onClick={togglePromptBar}
              className="ml-auto text-[10px] text-white/30 hover:text-white/50"
            >
              收起
            </button>
          </div>

          {/* Text area */}
          <div className="flex gap-2">
            <textarea
              value={promptBarContent}
              onChange={(e) => setPromptBarContent(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                promptBarMode === 'ai'
                  ? '输入 AI 指令，如 "让这个镜头更有戏剧张力"...'
                  : '直接编辑 visual prompt...'
              }
              className="flex-1 resize-none rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-[12px] text-white/80 placeholder:text-white/20 focus:outline-none focus:border-cyan-500/30 min-h-[80px]"
              rows={3}
            />
            <button
              onClick={handleSubmit}
              disabled={!promptBarContent.trim()}
              className="self-end rounded-lg bg-cyan-500/20 px-4 py-2 text-[11px] font-medium text-cyan-100 hover:bg-cyan-500/30 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {promptBarMode === 'ai' ? '发送' : '应用'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export const PromptBar = memo(PromptBarInner);
