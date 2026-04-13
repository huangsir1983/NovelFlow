/**
 * videoPromptAssembly — Pure functions for video generation prompt assembly.
 *
 * Constructs structured prompts and image reference lists from upstream
 * canvas node metadata (shot, scene, characters, first frame).
 */

import type { VideoGenerationNodeData, VideoImageRef } from '../types/canvas';

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
