'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useProjectStore } from '../stores/projectStore';
import { fetchAPI, API_BASE_URL } from '../lib/api';

const AUTO_SAVE_INTERVAL = 30_000; // 30 seconds

/**
 * Auto-save hook — periodically syncs frontend store delta to the server.
 *
 * Architecture:
 *   SSE events → store (in-memory, instant display)
 *   Every 30s  → POST /api/projects/{id}/sync (persist delta to server DB)
 *   Page load  → GET assets from server (restore)
 *
 * Only syncs data collections (characters, scenes, locations, props, variants).
 * Pipeline-generated data is already written to DB by the backend;
 * this hook ensures any client-side additions/edits are also persisted.
 */
export function useAutoSave(projectId: string | null) {
  const store = useProjectStore();
  const lastSnapshotRef = useRef<string>('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const buildSnapshot = useCallback(() => {
    return JSON.stringify({
      characters: store.characters.length,
      scenes: store.scenes.length,
      locations: store.locations.length,
      props: store.props.length,
      variants: store.characterVariants.length,
    });
  }, [store.characters.length, store.scenes.length, store.locations.length, store.props.length, store.characterVariants.length]);

  const syncToServer = useCallback(async () => {
    if (!projectId || !store.project) return;

    const currentSnapshot = buildSnapshot();
    // Skip if nothing changed
    if (currentSnapshot === lastSnapshotRef.current) return;

    try {
      await fetchAPI(`/api/projects/${projectId}/sync`, {
        method: 'POST',
        body: JSON.stringify({
          characters: store.characters,
          scenes: store.scenes,
          locations: store.locations,
          props: store.props,
          character_variants: store.characterVariants,
        }),
      });
      lastSnapshotRef.current = currentSnapshot;
    } catch {
      // Silent fail — will retry next interval
    }
  }, [projectId, store, buildSnapshot]);

  // Start auto-save timer
  useEffect(() => {
    if (!projectId) return;

    // Take initial snapshot (so we don't sync on first tick if nothing changed)
    lastSnapshotRef.current = buildSnapshot();

    timerRef.current = setInterval(syncToServer, AUTO_SAVE_INTERVAL);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [projectId, syncToServer, buildSnapshot]);

  // Save on page unload
  useEffect(() => {
    if (!projectId) return;

    const handleBeforeUnload = () => {
      // Use sendBeacon for reliable delivery during unload
      const data = JSON.stringify({
        characters: store.characters,
        scenes: store.scenes,
        locations: store.locations,
        props: store.props,
        character_variants: store.characterVariants,
      });
      navigator.sendBeacon(
        `${API_BASE_URL}/api/projects/${projectId}/sync`,
        new Blob([data], { type: 'application/json' }),
      );
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [projectId, store]);

  return { syncNow: syncToServer };
}
