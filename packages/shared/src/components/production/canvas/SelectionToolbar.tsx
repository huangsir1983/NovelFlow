'use client';

import { memo } from 'react';

interface SelectionToolbarProps {
  selectedCount: number;
  onRunSelected: () => void;
  onDeleteSelected: () => void;
  onGroupSelected: () => void;
}

function SelectionToolbarComponent({
  selectedCount,
  onRunSelected,
  onDeleteSelected,
  onGroupSelected,
}: SelectionToolbarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="absolute top-3 left-1/2 -translate-x-1/2 z-40 flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#0a0f1a]/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl">
      <span className="text-[11px] text-white/50 mr-2">
        已选 {selectedCount} 个节点
      </span>
      <button
        onClick={onRunSelected}
        className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition-colors"
      >
        运行
      </button>
      <button
        onClick={onGroupSelected}
        className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-white/5 text-white/60 hover:bg-white/10 transition-colors"
      >
        分组
      </button>
      <button
        onClick={onDeleteSelected}
        className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-red-500/10 text-red-400/80 hover:bg-red-500/20 transition-colors"
      >
        删除
      </button>
    </div>
  );
}

export const SelectionToolbar = memo(SelectionToolbarComponent);
