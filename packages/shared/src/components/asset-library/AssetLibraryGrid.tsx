'use client';

import React, { useCallback, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AssetListCard } from './AssetCard';
import type { CardType } from './AssetCard';
import { AssetDetailPanel } from './AssetDetailPanel';
import { useProjectStore } from '../../stores/projectStore';
import type { AssetFilter } from '../../stores/projectStore';
import { fetchAPI } from '../../lib/api';
import type { Character, Scene, Location, Prop, CharacterVariant } from '../../types/project';

interface AssetItem {
  id: string;
  key: string;
  cardType: CardType;
  data: Record<string, unknown>;
}

interface AssetLibraryGridProps {
  characters: Character[];
  scenes: Scene[];
  locations: Location[];
  props: Prop[];
  characterVariants: CharacterVariant[];
  assetFilter: AssetFilter;
  importing: boolean;
  locked?: boolean;
  projectId?: string;
  onFileUpload?: (file: File) => void;
  uploadDisabled?: boolean;
  uploadLabel?: string;
  uploadHint?: string;
}

function buildItems(
  characters: Character[],
  _scenes: Scene[],
  locations: Location[],
  props: Prop[],
  _characterVariants: CharacterVariant[],
  filter: AssetFilter,
): AssetItem[] {
  const items: AssetItem[] = [];

  if (filter === 'all' || filter === 'character') {
    characters.forEach((c) =>
      items.push({
        id: c.id,
        key: `character-${c.id}`,
        cardType: 'character',
        data: c as unknown as Record<string, unknown>,
      }),
    );
  }

  if (filter === 'all' || filter === 'location') {
    locations.forEach((l) =>
      items.push({
        id: l.id,
        key: `location-${l.id}`,
        cardType: 'location',
        data: l as unknown as Record<string, unknown>,
      }),
    );
  }

  if (filter === 'all' || filter === 'prop') {
    props.forEach((p) =>
      items.push({
        id: p.id,
        key: `prop-${p.id}`,
        cardType: 'prop',
        data: p as unknown as Record<string, unknown>,
      }),
    );
  }

  return items;
}

const DEFAULT_LIST_WIDTH = 420;
const MIN_LIST_WIDTH = 260;
const MAX_LIST_WIDTH = 700;

export function AssetLibraryGrid({
  characters,
  scenes,
  locations,
  props,
  characterVariants,
  assetFilter,
  importing,
  locked,
  projectId,
  onFileUpload,
  uploadDisabled,
  uploadLabel,
  uploadHint,
}: AssetLibraryGridProps) {
  const { selectedAssetId, selectAsset, assetImages, assetLoadingSlots, removeCharacter, removeLocation, removeProp, removeCharacterVariant } = useProjectStore();
  const [listWidth, setListWidth] = useState(DEFAULT_LIST_WIDTH);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(0);
  const [deleteConfirm, setDeleteConfirm] = useState<{ item: AssetItem; relatedScenes: string[] } | null>(null);

  // Find scenes related to an asset
  const findRelatedScenes = useCallback((item: AssetItem): string[] => {
    const name = (item.data.name as string) || (item.data.character_name as string) || '';
    if (!name) return [];
    return scenes.filter(s => {
      if (item.cardType === 'character' || item.cardType === 'variant') {
        return s.characters_present?.includes(name);
      }
      if (item.cardType === 'location') {
        return s.location === name;
      }
      if (item.cardType === 'prop') {
        return s.key_props?.includes(name);
      }
      return false;
    }).map(s => s.heading || s.location || `场景${s.order ?? ''}`);
  }, [scenes]);

  const handleDeleteRequest = useCallback((item: AssetItem) => {
    const relatedScenes = findRelatedScenes(item);
    setDeleteConfirm({ item, relatedScenes });
  }, [findRelatedScenes]);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteConfirm || !projectId) return;
    const { item } = deleteConfirm;
    const typePathMap: Record<string, string> = {
      character: 'characters',
      location: 'locations',
      prop: 'props',
      variant: 'variants',
    };
    const path = typePathMap[item.cardType];
    if (!path) return;
    try {
      await fetchAPI(`/api/projects/${projectId}/${path}/${item.id}`, { method: 'DELETE' });
      if (item.cardType === 'character') removeCharacter(item.id);
      else if (item.cardType === 'location') removeLocation(item.id);
      else if (item.cardType === 'prop') removeProp(item.id);
      else if (item.cardType === 'variant') removeCharacterVariant(item.id);
    } catch (err) {
      console.error('Delete asset failed:', err);
    }
    setDeleteConfirm(null);
  }, [deleteConfirm, projectId, removeCharacter, removeLocation, removeProp, removeCharacterVariant]);

  const isEmpty = characters.length === 0 && scenes.length === 0 && locations.length === 0 && props.length === 0 && characterVariants.length === 0;

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && onFileUpload) onFileUpload(file);
    },
    [onFileUpload],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  // --- Resize drag handlers ---
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = listWidth;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const delta = ev.clientX - startX.current;
      const next = Math.max(MIN_LIST_WIDTH, Math.min(MAX_LIST_WIDTH, startW.current + delta));
      setListWidth(next);
    };

    const onUp = () => {
      dragging.current = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [listWidth]);

  if (isEmpty && !importing) {
    return (
      <div
        className="flex h-full items-center justify-center p-8"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <div className="w-full max-w-md rounded-xl border-2 border-dashed border-white/[0.08] p-12 text-center transition-colors hover:border-white/[0.15]">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-brand/10">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-brand">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <p className="text-sm font-medium text-white/60">{uploadLabel || '拖放小说文件到此处'}</p>
          <p className="mt-1 text-xs text-white/30">{uploadHint || '支持 .txt 格式'}</p>
          {onFileUpload && (
            <label className={`mt-4 inline-block cursor-pointer rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-light ${uploadDisabled ? 'pointer-events-none opacity-50' : ''}`}>
              选择文件
              <input
                type="file"
                className="hidden"
                accept=".txt,.md"
                disabled={uploadDisabled}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onFileUpload(file);
                }}
              />
            </label>
          )}
        </div>
      </div>
    );
  }

  const items = buildItems(characters, scenes, locations, props, characterVariants, assetFilter);

  return (
    <div className="relative flex h-full">
      {/* Lock overlay */}
      {locked && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <svg className="h-10 w-10 text-white/40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <p className="text-sm text-white/50">剧本生成中，资产库已锁定</p>
          </div>
        </div>
      )}
      {/* Left: Asset list */}
      <div
        className="shrink-0 overflow-y-auto border-r border-white/[0.06] p-3 scrollbar-thin"
        style={{ width: listWidth }}
      >
        <div className="flex flex-col gap-1">
          {items.map((item) => {
            const previewImage = assetImages[item.id]?.front_full || assetImages[item.id]?.front || assetImages[item.id]?.east;
            const isGenerating = (assetLoadingSlots[item.id]?.size ?? 0) > 0;
            const hasPanorama = item.cardType === 'location' && !!assetImages[item.id]?.panorama;
            return (
              <AssetListCard
                key={item.key}
                cardType={item.cardType}
                data={item.data}
                selected={selectedAssetId === item.id}
                previewImage={previewImage}
                isGenerating={isGenerating}
                hasPanorama={hasPanorama}
                onDelete={() => handleDeleteRequest(item)}
                onClick={() => selectAsset(item.id, item.cardType)}
              />
            );
          })}
          {items.length === 0 && importing && (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-2">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/10 border-t-brand" />
                <span className="text-xs text-white/30">导入中...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Resize handle */}
      <div
        className="relative z-10 w-1 shrink-0 cursor-col-resize bg-transparent hover:bg-brand/30 active:bg-brand/50 transition-colors"
        onMouseDown={onResizeStart}
      >
        <div className="absolute inset-y-0 -left-1 -right-1" />
      </div>

      {/* Right: Detail panel */}
      <div className="flex-1 overflow-hidden">
        <AssetDetailPanel
          characters={characters}
          scenes={scenes}
          locations={locations}
          props={props}
          projectId={projectId}
        />
      </div>

      {/* Delete confirmation dialog */}
      {deleteConfirm && typeof document !== 'undefined' && createPortal(
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 99999, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
          onClick={() => setDeleteConfirm(null)}
        >
          <div
            className="w-80 rounded-xl border border-white/[0.10] bg-[#1a1a2e] p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h4 className="mb-3 text-sm font-semibold text-white/90">确认删除</h4>
            <p className="mb-2 text-xs text-white/60">
              确定要删除「{(deleteConfirm.item.data.name as string) || (deleteConfirm.item.data.character_name as string) || '未知'}」吗？
            </p>
            {deleteConfirm.relatedScenes.length > 0 && (
              <div className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] p-2.5">
                <p className="mb-1.5 text-[11px] font-medium text-amber-300/80">
                  该资产参与了 {deleteConfirm.relatedScenes.length} 个场景：
                </p>
                <div className="flex flex-wrap gap-1">
                  {deleteConfirm.relatedScenes.slice(0, 8).map((s) => (
                    <span key={s} className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300/70">{s}</span>
                  ))}
                  {deleteConfirm.relatedScenes.length > 8 && (
                    <span className="text-[10px] text-amber-300/50">+{deleteConfirm.relatedScenes.length - 8} 个</span>
                  )}
                </div>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteConfirm(null)}
                className="rounded-lg px-4 py-1.5 text-xs text-white/40 hover:bg-white/[0.06] transition-colors"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="rounded-lg bg-red-500/20 px-4 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/30 transition-colors"
              >
                删除
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
}
