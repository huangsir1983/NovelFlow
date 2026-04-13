'use client';

import { useEffect, useRef } from 'react';
import type { Edge } from '@xyflow/react';
import { useProjectStore } from '../stores/projectStore';
import { useBoardStore } from '../stores/boardStore';
import { useCanvasStore } from '../stores/canvasStore';
import { buildCanvasGraph, type SceneInput, type ShotInput, type CharacterMapEntry, type LocationDetailEntry, shotNodeId, videoNodeId } from '../lib/canvasLayout';
import { API_BASE_URL, normalizeStorageUrl } from '../lib/api';

/** Apply saved node execution results to freshly built nodes + propagate outputs downstream */
type SavedNodeResult = { node_type: string; input_snapshot: Record<string, unknown>; output_snapshot: Record<string, unknown> };

function _applySavedResults(
  nodes: import('@xyflow/react').Node[],
  edges: Edge[],
  saved: Record<string, SavedNodeResult> | null,
): import('@xyflow/react').Node[] {
  if (!saved || Object.keys(saved).length === 0) return nodes;

  // Step 1: Build output URL map for all saved nodes
  const outputMap = new Map<string, { url?: string; key?: string }>();
  for (const [nodeId, rec] of Object.entries(saved)) {
    if (!rec.output_snapshot) continue;
    const out = rec.output_snapshot;
    // Normalize: some handlers use outputStorageKey, others use storage_key
    const key = (out.outputStorageKey || out.storage_key) as string | undefined;
    const url = key ? `${API_BASE_URL}/uploads/${key}` : (out.outputImageUrl as string | undefined);
    if (url || key) outputMap.set(nodeId, { url, key });
  }

  // Step 2: Build downstream propagation map (source → set of target node IDs)
  const downstreamInputs = new Map<string, { url?: string; key?: string }>();
  for (const e of edges) {
    const src = outputMap.get(e.source);
    if (src) downstreamInputs.set(e.target, src);
  }

  // Step 2b: Build DirectorStage3D → GeminiComposite propagation map
  const stageToComposite = new Map<string, {
    sceneStorageKey: string;
    characterScreenshots: Array<Record<string, unknown>>;
    stageCharacters: unknown[];
    sceneDescription: string;
  }>();
  for (const [nodeId, rec] of Object.entries(saved)) {
    if (rec.node_type !== 'directorStage3D') continue;
    if (!rec.output_snapshot?.outputStorageKey) continue;
    const inp = rec.input_snapshot || {};
    for (const e of edges) {
      if (e.source === nodeId) {
        stageToComposite.set(e.target, {
          sceneStorageKey: rec.output_snapshot.outputStorageKey as string,
          characterScreenshots: (inp.characterScreenshots || []) as Array<Record<string, unknown>>,
          stageCharacters: (inp.stageCharacters || []) as unknown[],
          sceneDescription: (inp.sceneDescription || '') as string,
        });
      }
    }
  }

  // Step 3: Patch nodes — restore saved results + propagate inputs to downstream
  return nodes.map((n) => {
    let patched = n;

    // Apply saved execution result to this node
    const rec = saved[n.id];
    if (rec?.output_snapshot) {
      const out = rec.output_snapshot;
      const inp = rec.input_snapshot || {};
      const patch: Record<string, unknown> = { status: 'success', progress: 100 };
      // Normalize: some handlers use outputStorageKey, others use storage_key
      const storageKey = (out.outputStorageKey || out.storage_key) as string | undefined;
      if (storageKey) {
        patch.outputStorageKey = storageKey;
        patch.outputImageUrl = `${API_BASE_URL}/uploads/${storageKey}`;
      }
      if (out.outputImageUrl) patch.outputImageUrl = out.outputImageUrl;
      if (out.outputPngUrl) patch.outputPngUrl = out.outputPngUrl;
      // SceneBG nodes store screenshot in screenshotUrl field
      if (rec.node_type === 'sceneBG' && storageKey) {
        patch.screenshotUrl = `${API_BASE_URL}/uploads/${storageKey}`;
        patch.panoramaStorageKey = storageKey as string;
      }
      // Pose3D nodes: restore screenshot + joint angles
      if (rec.node_type === 'pose3D' && storageKey) {
        patch.screenshotUrl = `${API_BASE_URL}/uploads/${storageKey}`;
        patch.screenshotStorageKey = storageKey as string;
      }
      // DirectorStage3D nodes: restore screenshot + stageCharacters + character screenshots
      if (rec.node_type === 'directorStage3D' && storageKey) {
        patch.screenshotStorageKey = storageKey as string;
        // Restore stageCharacters (positions, poses, joints)
        if (inp.stageCharacters && Array.isArray(inp.stageCharacters)) {
          patch.stageCharacters = inp.stageCharacters;
        }
        // Restore character screenshots with persistent URLs
        if (inp.characterScreenshots && Array.isArray(inp.characterScreenshots)) {
          patch.characterScreenshots = (inp.characterScreenshots as Array<Record<string, unknown>>).map(cs => ({
            ...cs,
            screenshot: cs.storageKey ? '' : (cs.screenshot || ''), // base64 not persisted; will use storageKey
          }));
        }
        // Restore scene description
        if (inp.sceneDescription) patch.sceneDescription = inp.sceneDescription;
      }
      // GeminiComposite nodes: restore output image + input context for regeneration
      if (rec.node_type === 'geminiComposite' && storageKey) {
        patch.outputStorageKey = storageKey;
        patch.outputImageUrl = `${API_BASE_URL}/uploads/${storageKey}`;
        // Restore input context so regeneration works without upstream re-capture
        if (inp.sceneScreenshotStorageKey) patch.sceneScreenshotStorageKey = inp.sceneScreenshotStorageKey;
        if (inp.sceneDescription) patch.sceneDescription = inp.sceneDescription;
        if (inp.characterMappings && Array.isArray(inp.characterMappings)) {
          patch.characterMappings = inp.characterMappings;
        }
      }
      // VideoGeneration nodes: restore video URL + prompt state
      if (rec.node_type === 'videoGeneration') {
        if (out.video_url) { patch.videoUrl = out.video_url; patch.status = 'success'; }
        if (out.task_id) patch.seedanceTaskId = out.task_id;
        if (inp.assembledPrompt) patch.assembledPrompt = inp.assembledPrompt;
        if (inp.imageRefs) patch.imageRefs = inp.imageRefs;
        if (inp.ratio) patch.ratio = inp.ratio;
        if (inp.durationSeconds) patch.durationSeconds = inp.durationSeconds;
      }
      if (inp.jointAngles) patch.jointAngles = inp.jointAngles;
      if (inp.azimuth !== undefined) patch.azimuth = inp.azimuth;
      if (inp.elevation !== undefined) patch.elevation = inp.elevation;
      if (inp.distance !== undefined) patch.distance = inp.distance;
      if (inp.targetAngle) patch.targetAngle = inp.targetAngle;
      if (inp.expressionPrompt) patch.expressionPrompt = inp.expressionPrompt;
      if (inp.scaleFactor) patch.scaleFactor = inp.scaleFactor;
      if (inp.processType) patch.processType = inp.processType;
      patched = { ...patched, data: { ...patched.data, ...patch } };
    }

    // Propagate upstream output as this node's input
    const upstream = downstreamInputs.get(n.id);
    if (upstream) {
      const inputPatch: Record<string, unknown> = {};
      if (upstream.url) inputPatch.inputImageUrl = upstream.url;
      if (upstream.key) inputPatch.inputStorageKey = upstream.key;
      patched = { ...patched, data: { ...patched.data, ...inputPatch } };
    }

    // Propagate DirectorStage3D → GeminiComposite (scene screenshot + character mappings)
    const stageData = stageToComposite.get(n.id);
    if (stageData && (patched.data as Record<string, unknown>).nodeType === 'geminiComposite') {
      const compositePatch: Record<string, unknown> = {
        sceneScreenshotStorageKey: stageData.sceneStorageKey,
      };
      if (stageData.sceneDescription) compositePatch.sceneDescription = stageData.sceneDescription;
      // Reconstruct characterMappings from saved character screenshots
      if (stageData.characterScreenshots.length > 0) {
        // Find CharacterProcess nodes upstream of DirectorStage3D for reference images
        // DirectorStage3D → this GeminiComposite, CharacterProcess → DirectorStage3D
        const stageNodeId = edges.find(e => e.target === n.id && stageToComposite.has(n.id))?.source;
        const charProcessNodes = stageNodeId
          ? nodes.filter(cn => {
              const isUpstream = edges.some(e => e.source === cn.id && e.target === stageNodeId);
              return isUpstream && (cn.data as Record<string, unknown>).nodeType === 'characterProcess';
            })
          : [];
        compositePatch.characterMappings = stageData.characterScreenshots.map(cs => {
          const cpNode = charProcessNodes.find(
            cn => (cn.data as Record<string, unknown>).characterName === cs.stageCharName,
          );
          const cpData = cpNode?.data as Record<string, unknown> | undefined;
          return {
            stageCharId: cs.stageCharId,
            stageCharName: cs.stageCharName,
            color: cs.color,
            poseScreenshot: '', // base64 not available after restore
            poseStorageKey: cs.storageKey || '',
            bbox: cs.bbox,
            referenceImageUrl: cpData?.visualRefUrl || '',
            referenceStorageKey: cpData?.visualRefStorageKey || '',
          };
        });
      }
      patched = { ...patched, data: { ...patched.data, ...compositePatch } };
    }

    return patched;
  });
}

/**
 * Auto-populate Composite layers from upstream nodes that already have output.
 * Each upstream source that has an image is upserted into the composite's layers.
 */
function _autoPopulateCompositeLayers(
  nodes: import('@xyflow/react').Node[],
  edges: Edge[],
  savedCompositeLayers?: Record<string, Array<Record<string, unknown>>>,
): import('@xyflow/react').Node[] {
  // Find all composite nodes
  const compositeNodes = nodes.filter(n => (n.data as Record<string, unknown>).nodeType === 'composite');
  if (compositeNodes.length === 0) return nodes;

  let result = nodes;
  for (const compNode of compositeNodes) {
    const compData = compNode.data as Record<string, unknown>;
    const currentLayers = (compData.layers || []) as Array<Record<string, unknown>>;

    // Priority: savedCompositeLayers (backend-persisted, has user positions) > currentLayers (in-memory)
    // Always use saved as base when available — it preserves user position/size/rotation edits.
    const saved = savedCompositeLayers?.[compNode.id];
    let layers: Array<Record<string, unknown>>;
    let changed: boolean;
    let imageUrlChanged = false; // track if any layer imageUrl actually changed
    if (saved && saved.length > 0) {
      // Start from saved layers (user-adjusted positions/sizes).
      // For each saved layer, prefer current imageUrl if newer, keep saved position/size.
      layers = saved.map(sl => {
        const cur = currentLayers.find(cl => cl.sourceNodeId === sl.sourceNodeId);
        // If current has a different (newer) imageUrl, use it; otherwise keep saved
        if (cur && cur.imageUrl && cur.imageUrl !== sl.imageUrl) {
          imageUrlChanged = true;
          return { ...sl, imageUrl: cur.imageUrl };
        }
        return { ...sl };
      });
      // Also add any current layers that are not in saved (new upstream sources)
      for (const cl of currentLayers) {
        if (!layers.some(l => l.sourceNodeId === cl.sourceNodeId)) {
          layers.push(cl);
          imageUrlChanged = true;
        }
      }
      changed = true;
    } else {
      layers = currentLayers.slice();
      changed = false;
    }

    // Find all edges pointing to this composite — upsert upstream outputs
    const incomingEdges = edges.filter(e => e.target === compNode.id);
    for (const edge of incomingEdges) {
      const srcNode = result.find(n => n.id === edge.source);
      if (!srcNode) continue;
      const srcData = srcNode.data as Record<string, unknown>;
      const imgUrl = (srcData.outputPngUrl || srcData.outputImageUrl || srcData.screenshotUrl) as string | undefined;
      if (!imgUrl) continue;

      // Determine layer type
      const nodeType = (srcData.nodeType || '') as string;
      const processType = (srcData.processType || '') as string;
      const isBgUpscale = nodeType === 'imageProcess' && processType === 'hdUpscale'
        && edges.some(e => e.target === edge.source && e.source.startsWith('scenebg-'));
      const layerType = (nodeType === 'sceneBG' || isBgUpscale) ? 'background' : 'character';

      // Upsert: find existing layer by sourceNodeId or type (for background)
      const existingIdx = layers.findIndex(l => l.sourceNodeId === edge.source);
      if (existingIdx >= 0) {
        // Only update imageUrl — never touch position/size/rotation
        if (layers[existingIdx].imageUrl !== imgUrl) {
          layers[existingIdx] = { ...layers[existingIdx], imageUrl: imgUrl };
          changed = true;
          imageUrlChanged = true;
        }
      } else {
        // Check if there's already a background layer from a different source
        const bgIdx = layerType === 'background' ? layers.findIndex(l => l.type === 'background') : -1;
        if (bgIdx >= 0) {
          // Update imageUrl + sourceNodeId, keep position/size
          if (layers[bgIdx].imageUrl !== imgUrl) imageUrlChanged = true;
          layers[bgIdx] = { ...layers[bgIdx], imageUrl: imgUrl, sourceNodeId: edge.source };
          changed = true;
        } else {
          // Brand new layer — use defaults
          layers.push({
            id: edge.source,
            type: layerType,
            sourceNodeId: edge.source,
            imageUrl: imgUrl,
            x: layerType === 'background' ? 0 : (1920 - 600) / 2,
            y: 0,
            width: layerType === 'background' ? 1920 : 600,
            height: 1080,
            rotation: 0,
            zIndex: layerType === 'background' ? 0 : layers.length,
            opacity: 1,
            visible: true,
            flipX: false,
          });
          changed = true;
          imageUrlChanged = true;
        }
      }
    }

    if (changed) {
      result = result.map(n => {
        if (n.id !== compNode.id) return n;
        const patch: Record<string, unknown> = { layers };
        // Only clear outputImageUrl when layer images actually changed (stale export);
        // preserve it on pure restore (refresh) so the preview keeps the editor export.
        if (imageUrlChanged) patch.outputImageUrl = undefined;
        return { ...n, data: { ...n.data, ...patch } };
      });
    }
  }
  return result;
}

/**
 * Apply disconnection state to raw edges: filter out broken segments, inject bypass edges.
 * Also merges in any user-created manual edges.
 */
function applyDisconnections(
  rawEdges: Edge[],
  manualEdges: Edge[],
  disconnectedSegments: Record<string, Set<string>>,
): Edge[] {
  const disconnectedShotIds = Object.keys(disconnectedSegments);

  // Start with raw pipeline edges, filtering out disconnected segments
  let result: Edge[];
  if (disconnectedShotIds.length === 0) {
    result = [...rawEdges];
  } else {
    result = rawEdges.filter((e) => {
      const edgeData = e.data as { shotId?: string; segment?: string } | undefined;
      if (!edgeData?.shotId || !edgeData?.segment) return true;
      const segs = disconnectedSegments[edgeData.shotId];
      return !segs || !segs.has(edgeData.segment);
    });

    // Add bypass dashed edges for disconnected shots
    for (const sid of disconnectedShotIds) {
      const segs = disconnectedSegments[sid];
      if (segs && segs.size > 0) {
        result.push({
          id: `bypass-${sid}`,
          source: shotNodeId(sid),
          target: videoNodeId(sid),
          type: 'bypass',
          data: { shotId: sid },
        });
      }
    }
  }

  // Append user-created manual edges
  for (const me of manualEdges) {
    if (!result.some((e) => e.id === me.id)) {
      result.push(me);
    }
  }

  return result;
}

/**
 * BFS: check if there's a directed path from `start` to `end` using
 * only non-bypass edges in the given edge list.
 */
function hasPath(edges: Edge[], start: string, end: string): boolean {
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (e.type === 'bypass') continue;
    const list = adj.get(e.source) || [];
    list.push(e.target);
    adj.set(e.source, list);
  }
  const visited = new Set<string>();
  const queue = [start];
  visited.add(start);
  while (queue.length > 0) {
    const node = queue.shift()!;
    if (node === end) return true;
    for (const next of adj.get(node) || []) {
      if (!visited.has(next)) {
        visited.add(next);
        queue.push(next);
      }
    }
  }
  return false;
}

/**
 * Syncs domain data (scenes/shots from projectStore + production state from boardStore)
 * into React Flow nodes/edges in canvasStore.
 *
 * IMPORTANT: Only rebuilds when domain data actually changes (scene/shot IDs or run/artifact keys).
 * Does NOT re-run on canvas UI interactions (clicks, drags, selections).
 * Reads positionCache at build time via store.getState() to avoid re-triggering.
 */
export function useCanvasSync() {
  const scenes = useProjectStore((s) => s.scenes);
  const shots = useProjectStore((s) => s.shots);
  const characters = useProjectStore((s) => s.characters);
  const locations = useProjectStore((s) => s.locations);
  const assetImages = useProjectStore((s) => s.assetImages);
  const assetImageKeys = useProjectStore((s) => s.assetImageKeys);
  const nodeRunsByShotId = useBoardStore((s) => s.nodeRunsByShotId);
  const artifactsByShotId = useBoardStore((s) => s.artifactsByShotId);
  const disconnectedSegments = useCanvasStore((s) => s.disconnectedSegments);
  const manualEdges = useCanvasStore((s) => s.manualEdges);

  const prevHashRef = useRef('');
  const rawEdgesRef = useRef<Edge[]>([]);
  const initializedRef = useRef(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Cache for persisted node results (fetched once, applied after every rebuild)
  const savedResultsRef = useRef<Record<string, SavedNodeResult> | null>(null);
  // Cache for persisted composite layer configurations
  const savedLayersRef = useRef<Record<string, Array<Record<string, unknown>>> | null>(null);
  const fetchedRef = useRef(false);

  // Effect 1: rebuild graph when domain data changes (debounced)
  useEffect(() => {
    const hash = JSON.stringify({
      sceneCount: scenes.length,
      sceneIds: scenes.map((s) => s.id).join(','),
      scenesWithScript: scenes.filter((s) => s.generated_script_json).length,
      shotCount: shots.length,
      shotIds: shots.map((s) => s.id).join(','),
      runKeys: Object.keys(nodeRunsByShotId).sort().join(','),
      artKeys: Object.keys(artifactsByShotId).sort().join(','),
      locPanorama: locations.map((l) => `${l.id}:${assetImages[l.id]?.['panorama'] ? '1' : '0'}`).join(','),
      charIds: characters.map((c) => c.id).join(','),
      locDetailIds: locations.map((l) => l.id).join(','),
    });

    if (hash === prevHashRef.current) return;

    // Debounce graph rebuild to avoid rapid sequential updates
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
    prevHashRef.current = hash;
    const { positionCache, setNodes, setEdges, disconnectedSegments: disc, manualEdges: me } = useCanvasStore.getState();

    const sceneInputs: SceneInput[] = scenes.map((s) => ({
      id: s.id,
      heading: s.heading || '',
      location: s.location || '',
      timeOfDay: s.time_of_day || '',
      description: s.description || '',
      characterNames: (s.characters_present || []) as string[],
      order: s.order ?? 0,
      coreEvent: s.core_event || '',
      emotionalPeak: s.emotional_peak || '',
      narrativeMode: s.narrative_mode || '',
      scriptJson: s.generated_script_json ? {
        beats: (s.generated_script_json.beats || []).map((b) => ({
          beat_id: b.beat_id || '',
          timestamp: b.timestamp || '',
          type: b.type || '',
          shots: (b.shots || []).map((sh) => ({
            shot_type: sh.shot_type || '',
            camera_move: sh.camera_move || '',
            angle: sh.angle || '',
            subject: sh.subject || '',
            action: sh.action || '',
            dialogue: sh.dialogue ? { character: sh.dialogue.character || '', line: sh.dialogue.line || '' } : null,
          })),
        })),
        duration_estimate_s: s.generated_script_json.duration_estimate_s,
        scene_summary: s.generated_script_json.scene_summary as unknown as SceneInput['scriptJson'] extends undefined ? never : NonNullable<SceneInput['scriptJson']>['scene_summary'],
      } : undefined,
    }));

    const shotInputs: ShotInput[] = shots.map((s) => ({
      id: s.id,
      sceneId: s.scene_id || '',
      shotNumber: s.shot_number || 0,
      framing: s.framing || '',
      cameraAngle: s.camera_angle || '',
      cameraMovement: s.camera_movement || '',
      description: s.description || '',
      thumbnailUrl: undefined,
      visualPrompt: s.visual_prompt || '',
      charactersInFrame: s.characters_in_frame || [],
      durationEstimate: s.duration_estimate || '',
    }));

    // Build location name → panorama URL/key map (with viewpoints)
    const locationPanoramaMap: Record<string, { locationId: string; panoramaUrl?: string; panoramaStorageKey?: string; depthMapUrl?: string; depthMapStorageKey?: string; viewpoints?: import('../types/canvas').ViewPoint[] }> = {};
    for (const loc of locations) {
      const imgs = assetImages[loc.id];
      const keys = assetImageKeys[loc.id];
      const panoramaUrl = normalizeStorageUrl(imgs?.['panorama']);
      const panoramaStorageKey = keys?.['panorama'];
      const depthMapUrl = normalizeStorageUrl(imgs?.['panorama_depth']);
      const depthMapStorageKey = keys?.['panorama_depth'];
      // Map backend viewpoints (snake_case) to frontend ViewPoint (camelCase)
      const viewpoints = ((loc as unknown as Record<string, unknown>).viewpoints as Array<Record<string, unknown>> | undefined)?.map(vp => ({
        id: vp.id as string,
        label: vp.label as string,
        yaw: (vp.yaw as number) ?? 0,
        pitch: (vp.pitch as number) ?? 0,
        fov: (vp.fov as number) ?? 75,
        posX: (vp.pos_x as number) ?? 0,
        posY: (vp.pos_y as number) ?? 0,
        posZ: (vp.pos_z as number) ?? 0,
        correctionStrength: (vp.correction_strength as number) ?? 0.5,
        isDefault: (vp.is_default as boolean) ?? false,
      })) ?? [];
      if (panoramaUrl || panoramaStorageKey || depthMapUrl || depthMapStorageKey || viewpoints.length > 0) {
        locationPanoramaMap[loc.name] = { locationId: loc.id, panoramaUrl, panoramaStorageKey, depthMapUrl, depthMapStorageKey, viewpoints };
      }
    }

    // Build character name → visual data map
    const characterMap: Record<string, CharacterMapEntry> = {};
    for (const char of characters) {
      const imgs = assetImages[char.id];
      const keys = assetImageKeys[char.id];
      // Try multiple image slots — priority: visual_reference > front_full > front > main > any first available
      const rawVisualRefUrl = imgs?.['visual_reference'] || imgs?.['front_full'] || imgs?.['front'] || imgs?.['main']
        || (imgs ? Object.values(imgs)[0] : undefined);
      const visualRefStorageKey = keys?.['visual_reference'] || keys?.['front_full'] || keys?.['front'] || keys?.['main']
        || (keys ? Object.values(keys)[0] : undefined);
      // Only use rawVisualRefUrl if it's actually an image (http/data:/path), not a text description.
      // Fallback to storage key → /uploads/ URL when store cache is empty (e.g. after page reload).
      let visualRefUrl: string | undefined;
      if (rawVisualRefUrl && (rawVisualRefUrl.startsWith('http') || rawVisualRefUrl.startsWith('data:') || rawVisualRefUrl.includes('/uploads/'))) {
        visualRefUrl = normalizeStorageUrl(rawVisualRefUrl);
      } else if (visualRefStorageKey) {
        visualRefUrl = `${API_BASE_URL}/uploads/${visualRefStorageKey}`;
      }
      characterMap[char.name] = {
        id: char.id,
        name: char.name,
        appearance: char.appearance,
        costume: char.costume,
        visualRefUrl,
        visualRefStorageKey,
        negativePrompt: char.visual_prompt_negative,
        allImages: imgs,
        allImageKeys: keys,
      };
    }

    // Build location name → visual detail map
    const locationDetailMap: Record<string, LocationDetailEntry> = {};
    for (const loc of locations) {
      const imgs = assetImages[loc.id];
      const keys = assetImageKeys[loc.id];
      const rawLocUrl = imgs?.['main'] || imgs?.['east'];
      const locStorageKey = keys?.['main'] || keys?.['east'];
      let locVisualRefUrl: string | undefined;
      if (rawLocUrl && (rawLocUrl.startsWith('http') || rawLocUrl.startsWith('data:') || rawLocUrl.includes('/uploads/'))) {
        locVisualRefUrl = normalizeStorageUrl(rawLocUrl);
      } else if (locStorageKey) {
        locVisualRefUrl = `${API_BASE_URL}/uploads/${locStorageKey}`;
      }
      locationDetailMap[loc.name] = {
        visualDescription: loc.visual_description,
        mood: loc.mood,
        atmosphere: loc.atmosphere,
        lighting: loc.lighting,
        colorPalette: loc.color_palette,
        visualRefUrl: locVisualRefUrl,
        visualRefStorageKey: locStorageKey,
        negativePrompt: loc.visual_prompt_negative,
      };
    }

    // ── Match scene.location → location.name ──
    // Scenes use short forms (e.g. "沈府卧房"), locations use full forms
    // (e.g. "沈家卧房"). Apply synonym normalization + contains fallback.
    const _normLocName = (s: string): string =>
      s.replace(/侯府/g, '侯爵府').replace(/沈府/g, '沈家').replace(/高府/g, '高家');
    const locNameSet = new Set(locations.map(l => l.name));
    const locNames = locations.map(l => l.name);
    const sceneLocations = new Set(sceneInputs.map(s => s.location).filter(Boolean));
    for (const sceneLoc of sceneLocations) {
      if (locationPanoramaMap[sceneLoc] && locationDetailMap[sceneLoc]) continue;
      // Step 1: synonym normalization → exact match
      const norm = _normLocName(sceneLoc);
      let resolved = locNameSet.has(norm) ? norm : '';
      // Step 2: contains match (normalized scene.location ⊂ loc.name or reverse)
      if (!resolved) {
        for (const ln of locNames) {
          if (ln.includes(norm) || norm.includes(ln)) { resolved = ln; break; }
        }
      }
      // Step 3: bigram fallback for remaining edge cases
      if (!resolved) {
        let bestName = '';
        let bestScore = 2;
        for (const ln of locNames) {
          const a = norm, b = _normLocName(ln);
          let bigrams = 0;
          for (let i = 0; i < a.length - 1; i++) {
            if (b.includes(a.substring(i, i + 2))) bigrams++;
          }
          let chars = 0;
          for (const ch of a) { if (b.includes(ch)) chars++; }
          const score = bigrams * 5 + chars;
          if (score > bestScore) { bestScore = score; bestName = ln; }
        }
        if (bestName) resolved = bestName;
      }
      if (resolved) {
        if (!locationPanoramaMap[sceneLoc] && locationPanoramaMap[resolved]) {
          locationPanoramaMap[sceneLoc] = locationPanoramaMap[resolved];
        }
        if (!locationDetailMap[sceneLoc] && locationDetailMap[resolved]) {
          locationDetailMap[sceneLoc] = locationDetailMap[resolved];
        }
      }
    }

    const { nodes, edges } = buildCanvasGraph(sceneInputs, shotInputs, {
      positionCache,
      locationPanoramaMap,
      characterMap,
      locationDetailMap,
      artifactsByShotId: Object.fromEntries(
        Object.entries(artifactsByShotId).map(([k, v]) => [
          k,
          (v || []).map((a) => ({
            id: a.id || '',
            type: a.type || '',
            url: a.thumbnailText || undefined,
            status: a.status || 'draft',
          })),
        ]),
      ),
      nodeRunsByShotId: Object.fromEntries(
        Object.entries(nodeRunsByShotId).map(([k, v]) => [
          k,
          (v || []).map((r) => ({
            nodeKey: r.kind || '',
            status: r.status === 'succeeded' ? 'success' : r.status === 'failed' ? 'error' : r.status || 'idle',
            progress: undefined,
          })),
        ]),
      ),
    });

    rawEdgesRef.current = edges;

    // Snapshot current session's node runtime state before rebuild wipes it.
    // Keyed by nodeId → subset of data fields worth preserving.
    const prevNodes = useCanvasStore.getState().nodes;
    const prevDataMap = new Map<string, Record<string, unknown>>();
    for (const pn of prevNodes) {
      const pd = pn.data as Record<string, unknown>;
      const snap: Record<string, unknown> = {};
      // Preserve outputs produced during this session
      if (pd.outputImageUrl) snap.outputImageUrl = pd.outputImageUrl;
      if (pd.outputPngUrl) snap.outputPngUrl = pd.outputPngUrl;
      if (pd.outputStorageKey) snap.outputStorageKey = pd.outputStorageKey;
      if (pd.screenshotUrl) snap.screenshotUrl = pd.screenshotUrl;
      if (pd.panoramaStorageKey) snap.panoramaStorageKey = pd.panoramaStorageKey;
      if (pd.jointAngles && typeof pd.jointAngles === 'object' && Object.keys(pd.jointAngles as object).length > 0) snap.jointAngles = pd.jointAngles;
      if (pd.screenshotStorageKey) snap.screenshotStorageKey = pd.screenshotStorageKey;
      // Preserve propagated inputs
      if (pd.inputImageUrl) snap.inputImageUrl = pd.inputImageUrl;
      if (pd.inputStorageKey) snap.inputStorageKey = pd.inputStorageKey;
      // Preserve status
      if (pd.status === 'success' || pd.status === 'running' || pd.status === 'error') {
        snap.status = pd.status;
        if (pd.progress !== undefined) snap.progress = pd.progress;
      }
      // Preserve composite layers
      if (pd.nodeType === 'composite' && Array.isArray(pd.layers) && (pd.layers as unknown[]).length > 0) {
        snap.layers = pd.layers;
      }
      // Preserve character variant selection across rebuild
      if (pd.nodeType === 'characterProcess' && pd.selectedVariant && pd.selectedVariant !== 'visual_reference') {
        snap.selectedVariant = pd.selectedVariant;
        if (pd.visualRefUrl) snap.visualRefUrl = pd.visualRefUrl;
        if (pd.visualRefStorageKey) snap.visualRefStorageKey = pd.visualRefStorageKey;
      }
      // Preserve DirectorStage3D state across rebuild
      if (pd.nodeType === 'directorStage3D') {
        if (pd.stageCharacters && Array.isArray(pd.stageCharacters) && (pd.stageCharacters as unknown[]).length > 0) {
          snap.stageCharacters = pd.stageCharacters;
        }
        if (pd.characterScreenshots && Array.isArray(pd.characterScreenshots)) {
          snap.characterScreenshots = pd.characterScreenshots;
        }
        if (pd.screenshotBase64) snap.screenshotBase64 = pd.screenshotBase64;
        if (pd.sceneDescription) snap.sceneDescription = pd.sceneDescription;
      }
      // Preserve GeminiComposite state across rebuild
      if (pd.nodeType === 'geminiComposite') {
        if (pd.sceneScreenshotStorageKey) snap.sceneScreenshotStorageKey = pd.sceneScreenshotStorageKey;
        if (pd.sceneScreenshotBase64) snap.sceneScreenshotBase64 = pd.sceneScreenshotBase64;
        if (pd.characterMappings && Array.isArray(pd.characterMappings) && (pd.characterMappings as unknown[]).length > 0) {
          snap.characterMappings = pd.characterMappings;
        }
        if (pd.sceneDescription) snap.sceneDescription = pd.sceneDescription;
      }
      if (Object.keys(snap).length > 0) prevDataMap.set(pn.id, snap);
    }

    // Apply saved node results (if already fetched) before setting nodes
    let finalNodes = _applySavedResults(nodes, edges, savedResultsRef.current);

    // Restore current session state onto rebuilt nodes (only fields the rebuild didn't set)
    if (prevDataMap.size > 0) {
      finalNodes = finalNodes.map((n) => {
        const snap = prevDataMap.get(n.id);
        if (!snap) return n;
        const nd = n.data as Record<string, unknown>;
        const patch: Record<string, unknown> = {};
        for (const [key, val] of Object.entries(snap)) {
          if (nd[key] === undefined || nd[key] === null) patch[key] = val;
        }
        if (Object.keys(patch).length === 0) return n;
        return { ...n, data: { ...nd, ...patch } };
      });
    }

    // Auto-populate composite layers from upstream outputs + merge saved backend layers
    finalNodes = _autoPopulateCompositeLayers(finalNodes, edges, savedLayersRef.current ?? undefined);

    setNodes(finalNodes);
    setEdges(applyDisconnections(edges, me, disc));
    initializedRef.current = true;

    // Fetch saved results + composite layers once, then re-apply
    if (!fetchedRef.current) {
      fetchedRef.current = true;
      Promise.all([
        fetch(`${API_BASE_URL}/api/canvas/node-results`).then(r => r.ok ? r.json() : {}),
        fetch(`${API_BASE_URL}/api/canvas/composite-layers`).then(r => r.ok ? r.json() : {}),
      ])
        .then(([saved, savedLayers]: [Record<string, SavedNodeResult>, Record<string, Array<Record<string, unknown>>>]) => {
          if (Object.keys(saved).length > 0) savedResultsRef.current = saved;
          if (Object.keys(savedLayers).length > 0) savedLayersRef.current = savedLayers;
          if (!savedResultsRef.current && !savedLayersRef.current) return;
          // Re-apply to current nodes
          const { nodes: cur, setNodes: sn } = useCanvasStore.getState();
          const edgesNow = useCanvasStore.getState().edges;
          let patched = _applySavedResults(cur, edgesNow, savedResultsRef.current);
          patched = _autoPopulateCompositeLayers(patched, edgesNow, savedLayersRef.current ?? undefined);
          sn(patched);
        })
        .catch(() => {});
    }
    }, initializedRef.current ? 100 : 0); // first build is immediate, subsequent debounce 100ms

    return () => clearTimeout(debounceRef.current);
  }, [scenes, shots, characters, nodeRunsByShotId, artifactsByShotId, locations, assetImages, assetImageKeys]);

  // Effect 2: re-apply edges when disconnectedSegments or manualEdges change
  useEffect(() => {
    if (!initializedRef.current) return;
    const { setEdges } = useCanvasStore.getState();
    const computed = applyDisconnections(rawEdgesRef.current, manualEdges, disconnectedSegments);
    setEdges(computed);

    // Auto-clear bypass: if shot→video has a complete path (through non-bypass edges),
    // remove the disconnection state for that shot → bypass disappears on next render.
    const disconnectedShotIds = Object.keys(disconnectedSegments);
    if (disconnectedShotIds.length === 0) return;

    const toReconnect: string[] = [];
    for (const shotId of disconnectedShotIds) {
      if (hasPath(computed, shotNodeId(shotId), videoNodeId(shotId))) {
        toReconnect.push(shotId);
      }
    }
    if (toReconnect.length > 0) {
      // Batch reconnect in next microtask to avoid set-during-render
      Promise.resolve().then(() => {
        const { reconnectAllEdges } = useCanvasStore.getState();
        for (const sid of toReconnect) {
          reconnectAllEdges(sid);
        }
      });
    }
  }, [disconnectedSegments, manualEdges]);
}
