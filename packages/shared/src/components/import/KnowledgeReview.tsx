'use client';

import React from 'react';
import type { Character, Location } from '../../types/project';

interface KnowledgeReviewProps {
  characters: Character[];
  locations: Location[];
  worldBuilding: Record<string, unknown>;
  styleGuide: Record<string, unknown>;
  onConfirm?: () => void;
  confirmLabel?: string;
}

export function KnowledgeReview({
  characters,
  locations,
  worldBuilding,
  styleGuide,
  onConfirm,
  confirmLabel = '确认知识库',
}: KnowledgeReviewProps) {
  return (
    <div className="space-y-6">
      {/* Characters */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-white/70">
          角色 ({characters.length})
        </h3>
        <div className="space-y-2">
          {characters.map((char) => (
            <div
              key={char.id}
              className="rounded-lg border border-white/[0.06] bg-bg-1 p-3"
            >
              <div className="mb-1 flex items-center gap-2">
                <span className="font-medium text-white">{char.name}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    char.role === 'protagonist'
                      ? 'bg-indigo-500/20 text-indigo-400'
                      : char.role === 'antagonist'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-white/10 text-white/50'
                  }`}
                >
                  {char.role}
                </span>
              </div>
              {char.description && (
                <p className="text-xs text-white/40">{char.description}</p>
              )}
            </div>
          ))}
          {characters.length === 0 && (
            <p className="text-sm text-white/30">暂无角色数据</p>
          )}
        </div>
      </section>

      {/* Locations */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-white/70">
          场景地点 ({locations.length})
        </h3>
        <div className="space-y-2">
          {locations.map((loc) => (
            <div
              key={loc.id}
              className="rounded-lg border border-white/[0.06] bg-bg-1 p-3"
            >
              <span className="font-medium text-white">{loc.name}</span>
              {loc.description && (
                <p className="mt-1 text-xs text-white/40">{loc.description}</p>
              )}
            </div>
          ))}
          {locations.length === 0 && (
            <p className="text-sm text-white/30">暂无场景地点</p>
          )}
        </div>
      </section>

      {/* World Building */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-white/70">世界观</h3>
        <div className="rounded-lg border border-white/[0.06] bg-bg-1 p-3">
          {Object.keys(worldBuilding).length > 0 ? (
            <dl className="space-y-2 text-sm">
              {Object.entries(worldBuilding).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs text-white/40">{key}</dt>
                  <dd className="text-white/70">
                    {typeof value === 'string'
                      ? value
                      : Array.isArray(value)
                        ? value.join(', ')
                        : JSON.stringify(value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-white/30">暂无世界观数据</p>
          )}
        </div>
      </section>

      {/* Style Guide */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-white/70">写作风格</h3>
        <div className="rounded-lg border border-white/[0.06] bg-bg-1 p-3">
          {Object.keys(styleGuide).length > 0 ? (
            <dl className="space-y-2 text-sm">
              {Object.entries(styleGuide).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs text-white/40">{key}</dt>
                  <dd className="text-white/70">{String(value)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-white/30">暂无风格数据</p>
          )}
        </div>
      </section>

      {/* Confirm button */}
      {onConfirm && (
        <button
          type="button"
          onClick={onConfirm}
          className="w-full rounded-lg bg-gradient-to-r from-indigo-500 to-purple-500 px-6 py-3 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          {confirmLabel}
        </button>
      )}
    </div>
  );
}
