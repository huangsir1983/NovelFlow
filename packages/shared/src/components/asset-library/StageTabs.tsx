'use client';

import React from 'react';

export interface StageTabItem {
  id: string;
  label: string;
}

interface StageTabsProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  lockedTabs: string[];
  tabs?: StageTabItem[];
}

const DEFAULT_TABS: StageTabItem[] = [
  { id: 'info', label: '基础信息' },
  { id: 'script', label: '剧本构思' },
  { id: 'assets', label: '项目资产库' },
  { id: 'canvas', label: '造物画布' },
  { id: 'preview', label: '预编辑' },
];

export function StageTabs({ activeTab, onTabChange, lockedTabs, tabs = DEFAULT_TABS }: StageTabsProps) {
  return (
    <div className="flex items-center gap-4 rounded-lg bg-bg-2/60 p-1">
      {tabs.map((tab) => {
        const isLocked = lockedTabs.includes(tab.id);
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            disabled={isLocked}
            onClick={() => !isLocked && onTabChange(tab.id)}
            className={`
              flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-all
              ring-1 ring-white/10
              ${isActive
                ? 'bg-brand text-white shadow-sm shadow-brand/20'
                : isLocked
                  ? 'cursor-not-allowed text-white/20'
                  : 'text-white/50 hover:bg-white/5 hover:text-white/70'
              }
            `}
          >
            {isLocked && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            )}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
