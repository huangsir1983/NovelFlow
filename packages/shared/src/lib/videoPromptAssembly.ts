/**
 * videoPromptAssembly — Pure functions for video generation prompt assembly.
 *
 * Constructs structured prompts and image reference lists from upstream
 * canvas node metadata (shot, scene, characters, first frame).
 */

import type { VideoGenerationNodeData, VideoImageRef, VideoSegmentNodeData } from '../types/canvas';

const FIXED_PREFIX =
  '不要出现字幕，超细节刻画，保持人物一致性，场景为整体参考图，理解人物位置和大小，要构图合理，比例协调，位置固定不偏移，场景统一。位置固定不偏移，超细节刻画。保持人物一致性。';

/**
 * Build the image reference list from node data.
 * Order: firstFrame (if present) → characters with visualRefUrl.
 */
export function buildImageRefsFromNodeData(
  data: Partial<VideoGenerationNodeData>,
): VideoImageRef[] {
  const refs: VideoImageRef[] = [];

  // First frame image
  if (data.inputImageUrl) {
    refs.push({
      id: 'img-firstframe',
      label: '首帧图',
      type: 'firstFrame',
      url: data.inputImageUrl,
      storageKey: data.inputStorageKey,
    });
  }

  // Character reference images
  const charRefs = data.characterRefs || [];
  for (const cr of charRefs) {
    if (!cr.visualRefUrl) continue;
    refs.push({
      id: `img-char-${cr.name}`,
      label: cr.name,
      type: 'character',
      url: cr.visualRefUrl,
      storageKey: cr.visualRefStorageKey,
      characterName: cr.name,
    });
  }

  return refs;
}

/**
 * Assemble a structured video prompt from node metadata.
 *
 * Output format:
 * ```
 * 角色：图片2是苏阳、图片3是室友1
 * 首帧图：图片1是首帧图
 * 此组分镜预计时长5秒
 * 场景：学生宿舍内部
 * 时间：白天
 * 前置提示词：不要出现字幕...
 * 镜头1：5秒，景别（中景）；机位（侧面平视）；运镜（缓慢跟随转动）；画面承接：...
 * ```
 */
export function assembleVideoPrompt(
  data: Partial<VideoGenerationNodeData>,
): string {
  const imageRefs = buildImageRefsFromNodeData(data);
  const lines: string[] = [];

  // Build image index map: ref → "图片N" (1-based)
  const indexMap = new Map<string, number>();
  imageRefs.forEach((ref, i) => {
    indexMap.set(ref.id, i + 1);
  });

  // 角色行
  const charRefs = imageRefs.filter(r => r.type === 'character');
  if (charRefs.length > 0) {
    const charParts = charRefs.map(r => `图片${indexMap.get(r.id)}是${r.label}`);
    lines.push(`角色：${charParts.join('、')}`);
  }

  // 首帧图行
  const firstFrame = imageRefs.find(r => r.type === 'firstFrame');
  if (firstFrame) {
    lines.push(`首帧图：图片${indexMap.get(firstFrame.id)}是首帧图`);
  }

  // 时长
  const dur = data.durationSeconds || 0;
  if (dur > 0) {
    lines.push(`此组分镜预计时长${dur}秒`);
  }

  // 场景
  if (data.sceneLocation) {
    lines.push(`场景：${data.sceneLocation}`);
  }

  // 时间
  if (data.sceneTimeOfDay) {
    lines.push(`时间：${data.sceneTimeOfDay}`);
  }

  // 前置提示词
  lines.push(`前置提示词：${FIXED_PREFIX}`);

  // 镜头行
  const shotParts: string[] = [];
  if (dur > 0) shotParts.push(`${dur}秒`);
  if (data.shotFraming) shotParts.push(`景别（${data.shotFraming}）`);
  if (data.shotCameraAngle) shotParts.push(`机位（${data.shotCameraAngle}）`);
  if (data.shotCameraMovement) shotParts.push(`运镜（${data.shotCameraMovement}）`);

  // 画面承接 = shot description + dialogue
  const descParts: string[] = [];
  if (data.shotDescription) descParts.push(data.shotDescription);
  if (data.shotDialogue) descParts.push(`对白：${data.shotDialogue}`);

  let shotLine = `镜头1：${shotParts.join('，')}`;
  if (descParts.length > 0) {
    shotLine += `；画面承接：${descParts.join('。')}`;
  }
  lines.push(shotLine);

  return lines.join('\n');
}

/* ══════════════════════════════════════════════════════════════
   Multi-shot segment prompt assembly
   ══════════════════════════════════════════════════════════════ */

/**
 * Build deduplicated image reference list for a merged video segment.
 * Order: firstFrame (if present) → unique characters with visualRefUrl.
 */
export function buildSegmentImageRefs(
  data: Partial<VideoSegmentNodeData>,
): VideoImageRef[] {
  const refs: VideoImageRef[] = [];

  if (data.inputImageUrl) {
    refs.push({
      id: 'img-firstframe',
      label: '首帧图',
      type: 'firstFrame',
      url: data.inputImageUrl,
      storageKey: data.inputStorageKey,
    });
  }

  const seen = new Set<string>();
  for (const cr of data.characterRefs || []) {
    if (!cr.visualRefUrl || seen.has(cr.name)) continue;
    seen.add(cr.name);
    refs.push({
      id: `img-char-${cr.name}`,
      label: cr.name,
      type: 'character',
      url: cr.visualRefUrl,
      storageKey: cr.visualRefStorageKey,
      characterName: cr.name,
    });
  }

  return refs;
}

/**
 * Assemble a multi-shot structured prompt for a merged video segment.
 *
 * Output format:
 * ```
 * 角色：图片2是苏阳、图片3是室友1
 * 首帧图：图片1是首帧图
 * 此组分镜预计时长10秒
 * 场景：学生宿舍内部
 * 时间：白天
 * 前置提示词：不要出现字幕...
 * 镜头1：4秒，景别（中景）；机位（侧面平视）；运镜（缓慢跟随）；画面承接：...
 * 镜头2：3秒，景别（近景）；机位（正面平视）；过渡（自然衔接）；画面承接：...
 * ```
 */
export function assembleSegmentPrompt(
  data: Partial<VideoSegmentNodeData>,
): string {
  const imageRefs = buildSegmentImageRefs(data);
  const lines: string[] = [];
  const shots = data.shots || [];

  // Build image index map
  const indexMap = new Map<string, number>();
  imageRefs.forEach((ref, i) => {
    indexMap.set(ref.id, i + 1);
  });

  // 角色行
  const charRefs = imageRefs.filter(r => r.type === 'character');
  if (charRefs.length > 0) {
    const charParts = charRefs.map(r => `图片${indexMap.get(r.id)}是${r.label}`);
    lines.push(`角色：${charParts.join('、')}`);
  }

  // 首帧图行
  const firstFrame = imageRefs.find(r => r.type === 'firstFrame');
  if (firstFrame) {
    lines.push(`首帧图：图片${indexMap.get(firstFrame.id)}是首帧图`);
  }

  // 总时长 — prefer summing from shots for accuracy
  const totalDur = shots.reduce((sum, s) => sum + (s.durationSeconds || 0), 0)
    || data.totalDurationSeconds
    || 0;
  if (totalDur > 0) {
    lines.push(`此组分镜预计时长${totalDur}秒`);
  }

  // 场景
  if (data.sceneLocation) {
    lines.push(`场景：${data.sceneLocation}`);
  }

  // 时间
  if (data.sceneTimeOfDay) {
    lines.push(`时间：${data.sceneTimeOfDay}`);
  }

  // 前置提示词
  lines.push(`前置提示词：${FIXED_PREFIX}`);

  // 镜头行（多个）
  shots.forEach((shot, idx) => {
    const parts: string[] = [];
    if (shot.durationSeconds > 0) parts.push(`${shot.durationSeconds}秒`);
    if (shot.framing) parts.push(`景别（${shot.framing}）`);
    if (shot.cameraAngle) parts.push(`机位（${shot.cameraAngle}）`);
    if (shot.cameraMovement) parts.push(`运镜（${shot.cameraMovement}）`);

    // Transition hint for shots after the first
    if (idx > 0) {
      parts.push('过渡（自然衔接）');
    }

    // 画面承接
    const descParts: string[] = [];
    if (shot.description) descParts.push(shot.description);
    if (shot.dialogue) descParts.push(`对白：${shot.dialogue}`);

    let shotLine = `镜头${idx + 1}：${parts.join('，')}`;
    if (descParts.length > 0) {
      shotLine += `；画面承接：${descParts.join('。')}`;
    }
    lines.push(shotLine);
  });

  return lines.join('\n');
}

/* ══════════════════════════════════════════════════════════════
   Merged prompt from multiple VideoGenerationNode data
   ══════════════════════════════════════════════════════════════ */

/**
 * Build image reference list for merged nodes.
 * Order: shot1-firstFrame, shot2-firstFrame, ..., charA, charB, ...
 * Matches the index order used by assembleMergedPromptFromNodes.
 */
export function buildMergedImageRefs(
  videoNodes: Array<{ data: Partial<VideoGenerationNodeData> }>,
): VideoImageRef[] {
  const refs: VideoImageRef[] = [];

  // First frames per shot
  for (let i = 0; i < videoNodes.length; i++) {
    const d = videoNodes[i].data;
    if (d.inputImageUrl) {
      refs.push({
        id: `img-frame-${i}`,
        label: `镜头${i + 1}首帧`,
        type: 'firstFrame',
        url: d.inputImageUrl,
        storageKey: d.inputStorageKey,
      });
    }
  }

  // Deduplicated characters
  const seen = new Set<string>();
  for (const node of videoNodes) {
    for (const cr of node.data.characterRefs || []) {
      if (!cr.visualRefUrl || seen.has(cr.name)) continue;
      seen.add(cr.name);
      refs.push({
        id: `img-char-${cr.name}`,
        label: cr.name,
        type: 'character',
        url: cr.visualRefUrl,
        storageKey: cr.visualRefStorageKey,
        characterName: cr.name,
      });
    }
  }

  return refs;
}

/**
 * Assemble a structured multi-shot prompt from an array of VideoGenerationNodeData.
 * Each shot keeps its own first-frame image reference.
 *
 * Image index order: shot1-firstFrame, shot2-firstFrame, ..., charA, charB, ...
 */
export function assembleMergedPromptFromNodes(
  videoNodes: Array<{ data: Partial<VideoGenerationNodeData> }>,
): string {
  if (videoNodes.length === 0) return '';

  const lines: string[] = [];

  // Build image index: firstFrames first, then deduplicated characters
  let imgIdx = 1;
  const frameIndices: number[] = [];
  for (const node of videoNodes) {
    if (node.data.inputImageUrl) {
      frameIndices.push(imgIdx++);
    } else {
      frameIndices.push(0);
    }
  }

  const seenChars = new Set<string>();
  const charEntries: Array<{ name: string; imgIdx: number }> = [];
  for (const node of videoNodes) {
    for (const cr of node.data.characterRefs || []) {
      if (!cr.visualRefUrl || seenChars.has(cr.name)) continue;
      seenChars.add(cr.name);
      charEntries.push({ name: cr.name, imgIdx: imgIdx++ });
    }
  }

  // 角色行
  if (charEntries.length > 0) {
    lines.push(`角色：${charEntries.map(c => `图片${c.imgIdx}是${c.name}`).join('、')}`);
  }

  // 首帧行（每个镜头各自的首帧）
  for (let i = 0; i < videoNodes.length; i++) {
    if (frameIndices[i] > 0) {
      lines.push(`镜头${i + 1}首帧：图片${frameIndices[i]}`);
    }
  }

  // 总时长
  const totalDur = videoNodes.reduce((sum, n) => sum + (n.data.durationSeconds || 0), 0);
  if (totalDur > 0) {
    lines.push(`此组分镜预计时长${totalDur}秒`);
  }

  // 场景 & 时间
  const first = videoNodes[0].data;
  if (first.sceneLocation) lines.push(`场景：${first.sceneLocation}`);
  if (first.sceneTimeOfDay) lines.push(`时间：${first.sceneTimeOfDay}`);

  // 前置提示词
  lines.push(`前置提示词：${FIXED_PREFIX}`);

  // 镜头行
  videoNodes.forEach((node, idx) => {
    const d = node.data;
    const parts: string[] = [];
    if (d.durationSeconds && d.durationSeconds > 0) parts.push(`${d.durationSeconds}秒`);
    if (d.shotFraming) parts.push(`景别（${d.shotFraming}）`);
    if (d.shotCameraAngle) parts.push(`机位（${d.shotCameraAngle}）`);
    if (d.shotCameraMovement) parts.push(`运镜（${d.shotCameraMovement}）`);
    if (idx > 0) parts.push('过渡（自然衔接）');

    const descParts: string[] = [];
    if (d.shotDescription) descParts.push(d.shotDescription);
    if (d.shotDialogue) descParts.push(`对白：${d.shotDialogue}`);

    let shotLine = `镜头${idx + 1}：${parts.join('，')}`;
    if (descParts.length > 0) {
      shotLine += `；画面承接：${descParts.join('。')}`;
    }
    lines.push(shotLine);
  });

  return lines.join('\n');
}
