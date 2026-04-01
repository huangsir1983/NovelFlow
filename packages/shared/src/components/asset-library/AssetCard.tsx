'use client';

import React from 'react';
import { useProjectStore } from '../../stores/projectStore';

export type CardType = 'character' | 'scene' | 'location' | 'prop' | 'variant';

interface AssetCardProps {
  cardType: CardType;
  data: Record<string, unknown>;
  skeleton?: boolean;
}

const CARD_COLORS: Record<CardType, { accent: string; glow: string; badge: string; tag: string }> = {
  character: { accent: '#a855f7', glow: 'rgba(168,85,247,0.08)', badge: 'bg-purple-500/15 text-purple-300', tag: 'bg-purple-500/10 text-purple-300/80' },
  scene:     { accent: '#3b82f6', glow: 'rgba(59,130,246,0.08)',  badge: 'bg-blue-500/15 text-blue-300',   tag: 'bg-blue-500/10 text-blue-300/80' },
  location:  { accent: '#22c55e', glow: 'rgba(34,197,94,0.08)',   badge: 'bg-green-500/15 text-green-300', tag: 'bg-green-500/10 text-green-300/80' },
  prop:      { accent: '#f59e0b', glow: 'rgba(245,158,11,0.08)',  badge: 'bg-amber-500/15 text-amber-300', tag: 'bg-amber-500/10 text-amber-300/80' },
  variant:   { accent: '#ec4899', glow: 'rgba(236,72,153,0.08)',  badge: 'bg-pink-500/15 text-pink-300',   tag: 'bg-pink-500/10 text-pink-300/80' },
};

const CARD_LABELS: Record<CardType, string> = {
  character: '角色',
  scene: '场景',
  location: '地点',
  prop: '道具',
  variant: '变体',
};

function SkeletonLines() {
  return (
    <div className="space-y-2 pt-2">
      <div className="skeleton-shimmer h-3 w-4/5 rounded" />
      <div className="skeleton-shimmer h-3 w-3/5 rounded" />
    </div>
  );
}

/* ─── Character Card ─────────────────────────────────────── */

const ROLE_LABELS: Record<string, string> = {
  protagonist: '主角',
  antagonist: '反派',
  supporting: '配角',
  minor: '龙套',
};

const ROLE_COLORS: Record<string, string> = {
  protagonist: 'bg-amber-400/20 text-amber-300 ring-amber-400/30',
  antagonist: 'bg-red-400/20 text-red-300 ring-red-400/30',
  supporting: 'bg-sky-400/20 text-sky-300 ring-sky-400/30',
  minor: 'bg-white/10 text-white/50 ring-white/10',
};

function CharacterCard({ data, skeleton }: { data: Record<string, unknown>; skeleton?: boolean }) {
  const name = (data.name as string) || '未知';
  const role = (data.role as string) || '';
  const personality = (data.personality as string) || '';
  const ageRange = (data.age_range as string) || '';
  const castingTags = (data.casting_tags as string[]) || [];
  const aliases = (data.aliases as string[]) || [];
  const appearance = data.appearance as Record<string, string> | undefined;
  const desire = (data.desire as string) || '';
  const flaw = (data.flaw as string) || '';

  const initial = name.charAt(0);
  const displayTags = castingTags.slice(0, 3);
  const appearanceSummary = appearance
    ? [appearance.face, appearance.distinguishing_features].filter(Boolean).join('，')
    : '';

  return (
    <div className="relative p-4">
      {/* Header: Avatar + Name + Role */}
      <div className="flex items-start gap-3 mb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500/30 to-purple-600/10 text-base font-bold text-purple-200 ring-1 ring-purple-500/20">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="truncate text-[15px] font-semibold text-white/95">{name}</h4>
            {aliases.length > 0 && (
              <span className="truncate text-[10px] text-white/25">({aliases[0]})</span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-1.5">
            {role && (
              <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${ROLE_COLORS[role] || ROLE_COLORS.minor}`}>
                {ROLE_LABELS[role] || role}
              </span>
            )}
            {ageRange && (
              <span className="text-[10px] text-white/30">{ageRange}</span>
            )}
          </div>
        </div>
      </div>

      {skeleton ? <SkeletonLines /> : (
        <>
          {/* Casting tags */}
          {displayTags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {displayTags.map((tag) => (
                <span key={tag} className="rounded-full bg-purple-500/8 px-2 py-0.5 text-[10px] text-purple-300/70 ring-1 ring-inset ring-purple-500/10">
                  {tag}
                </span>
              ))}
              {castingTags.length > 3 && (
                <span className="rounded-full px-1.5 py-0.5 text-[10px] text-white/20">
                  +{castingTags.length - 3}
                </span>
              )}
            </div>
          )}

          {/* Personality */}
          {personality && (
            <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-white/40">{personality}</p>
          )}

          {/* Desire / Flaw chips */}
          {(desire || flaw) && (
            <div className="flex gap-2 mb-3">
              {desire && (
                <div className="min-w-0 flex-1">
                  <span className="text-[9px] font-medium uppercase tracking-wider text-white/20">欲望</span>
                  <p className="mt-0.5 truncate text-[11px] text-emerald-300/60">{desire}</p>
                </div>
              )}
              {flaw && (
                <div className="min-w-0 flex-1">
                  <span className="text-[9px] font-medium uppercase tracking-wider text-white/20">缺陷</span>
                  <p className="mt-0.5 truncate text-[11px] text-rose-300/60">{flaw}</p>
                </div>
              )}
            </div>
          )}

          {/* Appearance footer */}
          {appearanceSummary && (
            <div className="border-t border-white/[0.04] pt-2.5">
              <p className="line-clamp-2 text-[11px] leading-relaxed text-white/25">{appearanceSummary}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Scene Card ─────────────────────────────────────────── */

function SceneCard({ data, skeleton }: { data: Record<string, unknown>; skeleton?: boolean }) {
  const location = (data.location as string) || '';
  const heading = (data.heading as string) || '';
  const timeOfDay = (data.time_of_day as string) || '';
  const coreEvent = (data.core_event as string) || '';
  const tensionScore = data.tension_score as number | undefined;

  const TIME_ICONS: Record<string, string> = { day: '☀', night: '🌙', dawn: '🌅', dusk: '🌆' };

  return (
    <div className="p-4">
      <div className="flex items-start justify-between gap-2 mb-1">
        <h4 className="truncate text-[15px] font-semibold text-white/90">{heading || location || '场景'}</h4>
        {timeOfDay && (
          <span className="shrink-0 text-sm">{TIME_ICONS[timeOfDay] || ''}</span>
        )}
      </div>
      {location && heading && (
        <p className="mb-2 text-[11px] text-green-300/60">{location}</p>
      )}
      {skeleton ? <SkeletonLines /> : (
        <>
          {coreEvent && (
            <p className="mb-2.5 line-clamp-2 text-xs leading-relaxed text-white/40">{coreEvent}</p>
          )}
          {heading && location && !coreEvent && (
            <p className="mb-2.5 line-clamp-2 text-xs leading-relaxed text-white/40">{heading}</p>
          )}
          {tensionScore != null && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-white/25">张力</span>
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full bg-blue-400/60 transition-all"
                  style={{ width: `${Math.min(tensionScore * 100, 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-white/25">{tensionScore.toFixed(1)}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Location Card ──────────────────────────────────────── */

function LocationCard({ data, skeleton }: { data: Record<string, unknown>; skeleton?: boolean }) {
  const name = (data.name as string) || '未知';
  const mood = (data.mood as string) || '';
  const atmosphere = (data.atmosphere as string) || '';
  const visualDescription = (data.visual_description as string) || (data.description as string) || '';

  return (
    <div className="p-4">
      <h4 className="truncate text-[15px] font-semibold text-white/90">{name}</h4>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {mood && (
          <span className="inline-block rounded-md bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-300/80 ring-1 ring-inset ring-green-500/10">
            {mood}
          </span>
        )}
        {atmosphere && !mood && (
          <span className="inline-block rounded-md bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-300/80 ring-1 ring-inset ring-green-500/10">
            {atmosphere}
          </span>
        )}
      </div>
      {skeleton ? <SkeletonLines /> : visualDescription && (
        <p className="mt-2.5 line-clamp-3 text-xs leading-relaxed text-white/40">{visualDescription}</p>
      )}
    </div>
  );
}

/* ─── Prop Card ──────────────────────────────────────────── */

function PropCard({ data, skeleton }: { data: Record<string, unknown>; skeleton?: boolean }) {
  const name = (data.name as string) || '未知';
  const category = (data.category as string) || '';
  const isMotif = data.is_motif as boolean | undefined;
  const isMajor = data.is_major as boolean | undefined;
  const description = (data.description as string) || '';
  const appearanceCount = (data.appearance_count as number) || 0;

  return (
    <div className="p-4">
      <div className="flex items-start justify-between gap-2">
        <h4 className="truncate text-[15px] font-semibold text-white/90">{name}</h4>
        <div className="flex shrink-0 gap-1">
          {appearanceCount > 0 && (
            <span className="rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] text-blue-300">{appearanceCount}次</span>
          )}
          {isMotif && <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300">母题</span>}
          {isMajor && <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300">关键</span>}
        </div>
      </div>
      {category && (
        <span className="mt-1.5 inline-block rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300/80 ring-1 ring-inset ring-amber-500/10">
          {category}
        </span>
      )}
      {skeleton ? <SkeletonLines /> : description && (
        <p className="mt-2.5 line-clamp-3 text-xs leading-relaxed text-white/40">{description}</p>
      )}
    </div>
  );
}

/* ─── Variant Card ───────────────────────────────────────── */

function VariantCard({ data, skeleton }: { data: Record<string, unknown>; skeleton?: boolean }) {
  const characterName = (data.character_name as string) || '';
  const variantType = (data.variant_type as string) || '';
  const tags = (data.tags as string[]) || [];

  return (
    <div className="p-4">
      <h4 className="truncate text-[15px] font-semibold text-white/90">{characterName}</h4>
      {variantType && (
        <span className="mt-1.5 inline-block rounded-md bg-pink-500/10 px-1.5 py-0.5 text-[10px] font-medium text-pink-300/80 ring-1 ring-inset ring-pink-500/10">
          {variantType}
        </span>
      )}
      {skeleton ? <SkeletonLines /> : tags.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <span key={tag} className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-white/40">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Card Container ─────────────────────────────────────── */

const RENDERERS: Record<CardType, React.FC<{ data: Record<string, unknown>; skeleton?: boolean }>> = {
  character: CharacterCard,
  scene: SceneCard,
  location: LocationCard,
  prop: PropCard,
  variant: VariantCard,
};

export function AssetCard({ cardType, data, skeleton }: AssetCardProps) {
  const Renderer = RENDERERS[cardType];
  const colors = CARD_COLORS[cardType];

  return (
    <div
      className={`
        group relative overflow-hidden rounded-xl
        bg-gradient-to-b from-white/[0.03] to-transparent
        ring-1 ring-inset
        ${skeleton ? 'ring-white/[0.08] agent-pulse' : 'ring-white/[0.06]'}
        transition-all duration-200
        hover:ring-white/[0.12] hover:shadow-lg
      `}
      style={{
        backgroundColor: 'rgba(15,15,25,0.6)',
        backdropFilter: 'blur(8px)',
      }}
    >
      {/* Top accent line */}
      <div
        className="h-[2px] w-full opacity-60 transition-opacity group-hover:opacity-100"
        style={{ background: `linear-gradient(90deg, ${colors.accent}80, ${colors.accent}20, transparent)` }}
      />
      <Renderer data={data} skeleton={skeleton} />
    </div>
  );
}

/* ─── Asset List Card (for three-column layout) ──────────── */

interface AssetListCardProps {
  cardType: CardType;
  data: Record<string, unknown>;
  selected?: boolean;
  previewImage?: string;
  isGenerating?: boolean;
  onDelete?: () => void;
  onClick?: () => void;
}

export function AssetListCard({ cardType, data, selected, previewImage, isGenerating, onDelete, onClick }: AssetListCardProps) {
  const colors = CARD_COLORS[cardType];
  const characterVariants = useProjectStore((s) => s.characterVariants);
  const characterName = (data.character_name as string) || '';
  const variantName = (data.variant_name as string) || '';
  const name = cardType === 'variant'
    ? (characterName && variantName ? `${characterName} · ${variantName}` : characterName || variantName || '未知')
    : (data.name as string) || characterName || (data.heading as string) || (data.location as string) || '未知';
  const aliases = (data.aliases as string[]) || [];
  const role = (data.role as string) || '';
  const variantType = (data.variant_type as string) || '';
  const location = (data.location as string) || '';
  const coreEvent = (data.core_event as string) || '';
  const personality = (data.personality as string) || '';
  const description = (data.description as string) || (data.visual_description as string) || '';
  const mood = (data.mood as string) || '';
  const category = (data.category as string) || '';

  // Count variants for character cards
  const variantCount = cardType === 'character' && data.id
    ? characterVariants.filter(v => v.character_id === data.id).length
    : 0;

  const roleLabel = ROLE_LABELS[role] || role;
  const roleColor = ROLE_COLORS[role] || ROLE_COLORS.minor;

  const subtitle = cardType === 'variant' ? variantType : roleLabel;

  // Build a description line based on card type
  let descLine = '';
  if (cardType === 'scene') descLine = coreEvent;
  else if (cardType === 'character') descLine = personality;
  else if (cardType === 'location') descLine = mood || description;
  else if (cardType === 'prop') descLine = category;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick?.(); }}
      className={`
        group relative w-full rounded-lg text-left transition-all duration-300 cursor-pointer
        ${selected
          ? ''
          : 'hover:bg-white/[0.04] border border-white/[0.08]'
        }
      `}
      style={selected ? {
        border: `1.5px solid ${colors.accent}90`,
        boxShadow: `0 0 8px ${colors.accent}50, 0 0 20px ${colors.accent}25, 0 0 40px ${colors.accent}10`,
      } : undefined}
    >
      {/* Card content */}
      <div className="flex items-start gap-3 rounded-lg p-3">
        {/* Preview thumbnail */}
        <div
          className="flex items-center justify-center overflow-hidden rounded-lg"
          style={{
            width: '100px',
            height: '100px',
            minWidth: '100px',
            minHeight: '100px',
            backgroundColor: selected ? `${colors.accent}10` : 'rgba(255,255,255,0.04)',
          }}
        >
        {previewImage ? (
          <img src={previewImage.startsWith('data:') || previewImage.startsWith('http') ? previewImage : `data:image/png;base64,${previewImage}`} alt={name} style={{
            width: '100px',
            height: '100px',
            objectFit: 'cover',
            objectPosition: (cardType === 'character' || cardType === 'variant') ? 'top' : 'center',
          }} />
        ) : isGenerating ? (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1.5">
            <div
              className="h-6 w-6 animate-spin rounded-full"
              style={{
                border: '2px solid rgba(255,255,255,0.1)',
                borderTopColor: colors.accent,
              }}
            />
            <span className="text-[9px]" style={{ color: `${colors.accent}99` }}>生成中</span>
          </div>
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: `${colors.accent}60` }}>
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1 py-0.5">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-medium text-white/90">{name}</span>
          {aliases.length > 0 && (
            <span className="truncate text-[10px] text-white/25">({aliases[0]})</span>
          )}
        </div>
        <div className="mt-1.5 flex items-center gap-1.5">
          <span
            className="rounded px-1.5 py-0.5 text-[10px] font-medium"
            style={{
              backgroundColor: `${colors.accent}15`,
              color: `${colors.accent}cc`,
            }}
          >
            {CARD_LABELS[cardType]}
          </span>
          {subtitle && cardType !== 'scene' && cardType !== 'location' && cardType !== 'prop' && (
            <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${roleColor}`}>
              {subtitle}
            </span>
          )}
          {cardType === 'scene' && location && (
            <span className="rounded-md bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-300/80">
              {location}
            </span>
          )}
          {cardType === 'character' && variantCount > 0 && (
            <span className="rounded-md bg-pink-500/10 px-1.5 py-0.5 text-[10px] font-medium text-pink-300/80 ring-1 ring-inset ring-pink-500/10">
              {variantCount}变体
            </span>
          )}
        </div>
        {descLine && (
          <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-white/35">{descLine}</p>
        )}
      </div>
      </div>
      {/* Delete button — top right, visible on hover */}
      {onDelete && (
        <div
          style={{ position: 'absolute', top: 6, right: 6, zIndex: 10 }}
          className="opacity-0 transition-opacity group-hover:opacity-100"
        >
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-red-300 hover:bg-red-500/80 hover:text-white transition-colors"
          >
            删除
          </button>
        </div>
      )}
    </div>
  );
}
