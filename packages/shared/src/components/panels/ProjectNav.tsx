'use client';

import React from 'react';
import type { Chapter, Character } from '../../types/project';

interface NavItem {
  id: string;
  label: string;
  type: 'chapter' | 'character' | 'scene' | 'location';
  children?: NavItem[];
}

interface ProjectNavProps {
  chapters: Chapter[];
  characters: Character[];
  selectedId?: string;
  activeSection?: 'chapters' | 'characters' | 'scenes' | 'locations';
  onSelectItem?: (type: string, id: string) => void;
  onSectionChange?: (section: 'chapters' | 'characters' | 'scenes' | 'locations') => void;
}

export function ProjectNav({
  chapters,
  characters,
  selectedId,
  activeSection = 'chapters',
  onSelectItem,
  onSectionChange,
}: ProjectNavProps) {
  const sections = [
    { id: 'chapters' as const, label: '章节', count: chapters.length },
    { id: 'characters' as const, label: '角色', count: characters.length },
  ];

  return (
    <div className="flex h-full flex-col p-4">
      {/* Section tabs */}
      <div className="mb-4 flex gap-1 rounded-lg bg-bg-0/50 p-1">
        {sections.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => onSectionChange?.(section.id)}
            className={`flex-1 rounded-md px-2 py-1.5 text-xs transition-colors ${
              activeSection === section.id
                ? 'bg-indigo-500/20 text-indigo-400'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            {section.label} ({section.count})
          </button>
        ))}
      </div>

      {/* Chapter list */}
      {activeSection === 'chapters' && (
        <nav className="flex-1 space-y-1 overflow-auto">
          {chapters.map((chapter) => (
            <button
              key={chapter.id}
              type="button"
              onClick={() => onSelectItem?.('chapter', chapter.id)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                selectedId === chapter.id
                  ? 'bg-indigo-500/20 text-indigo-400'
                  : 'text-white/60 hover:bg-white/5 hover:text-white'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="truncate">{chapter.title || `第 ${chapter.order + 1} 章`}</span>
                <span className="shrink-0 text-xs text-white/20">{chapter.word_count}字</span>
              </div>
            </button>
          ))}
          {chapters.length === 0 && (
            <p className="py-4 text-center text-xs text-white/30">请先导入小说</p>
          )}
        </nav>
      )}

      {/* Character list */}
      {activeSection === 'characters' && (
        <nav className="flex-1 space-y-1 overflow-auto">
          {characters.map((char) => (
            <button
              key={char.id}
              type="button"
              onClick={() => onSelectItem?.('character', char.id)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                selectedId === char.id
                  ? 'bg-indigo-500/20 text-indigo-400'
                  : 'text-white/60 hover:bg-white/5 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="truncate">{char.name}</span>
                <span
                  className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] ${
                    char.role === 'protagonist'
                      ? 'bg-indigo-500/20 text-indigo-400'
                      : char.role === 'antagonist'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-white/10 text-white/40'
                  }`}
                >
                  {char.role}
                </span>
              </div>
            </button>
          ))}
          {characters.length === 0 && (
            <p className="py-4 text-center text-xs text-white/30">请先导入小说</p>
          )}
        </nav>
      )}
    </div>
  );
}
