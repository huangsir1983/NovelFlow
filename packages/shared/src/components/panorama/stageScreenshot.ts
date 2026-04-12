/**
 * Stage screenshot utilities — interleaved prompt+image part building
 * for Gemini multi-image generation from 3D director stage captures.
 */

// ── Types ────────────────────────────────────────────────────────

/** Mapping between a stage mannequin and a real character reference */
export interface CharacterMapping {
  stageCharId: string;
  stageCharName: string;
  stageCharColor: string;
  /** Real character name (e.g., "高令宁") */
  referenceCharName: string;
  /** @N index for the 3D pose screenshot in the prompt */
  poseImageIndex: number;
  /** @N index for the character reference photo in the prompt */
  refImageIndex: number;
}

/** Complete screenshot set from a 3D stage session */
export interface StageScreenshots {
  /** Full scene screenshot (all characters, no editor UI) */
  base: string;
  /** Per-character isolated screenshots */
  characters: Array<{
    stageCharId: string;
    stageCharName: string;
    color: string;
    screenshot: string;
  }>;
}

/** A single part in an interleaved Gemini request */
export interface GeminiPart {
  type: 'text' | 'image';
  content: string;       // text content or base64 image data
  mime_type?: string;     // only for type='image'
}

// ── Color name helper ────────────────────────────────────────────

const HEX_COLOR_MAP: Record<string, string> = {
  '#06b6d4': '蓝色', '#f472b6': '粉色', '#a78bfa': '紫色',
  '#34d399': '绿色', '#fbbf24': '金色', '#f87171': '红色',
  '#60a5fa': '蓝色',
};

function hexToColorName(hex: string): string {
  return HEX_COLOR_MAP[hex.toLowerCase()] || hex + '色';
}

// ── Interleaved parts builder (preferred) ────────────────────────

/**
 * Build Gemini parts: all images first, then a single text block
 * referencing each image by ordinal number (图1, 图2, 图3...).
 *
 * Image order:
 *   图1 = base scene screenshot
 *   图2 = char1 3D pose, 图3 = char1 reference photo
 *   图4 = char2 3D pose, 图5 = char2 reference photo
 *   ... and so on
 *
 * Text block: describes each image's role, then gives generation instructions.
 */
export function buildInterleavedParts(
  screenshots: StageScreenshots,
  characterData: Array<{
    stageCharId: string;
    referenceCharName: string;
    stageCharColor: string;
    poseScreenshot: string;
    referenceBase64: string;
  }>,
  sceneDescription?: string,
): GeminiPart[] {
  const parts: GeminiPart[] = [];

  // 1. All images first (ordered: base, then char pairs)
  parts.push({ type: 'image', content: screenshots.base, mime_type: 'image/jpeg' });
  for (const cd of characterData) {
    parts.push({ type: 'image', content: cd.poseScreenshot, mime_type: 'image/jpeg' });
    parts.push({ type: 'image', content: cd.referenceBase64, mime_type: 'image/jpeg' });
  }

  // 2. Single text block referencing images by ordinal
  const lines: string[] = [];

  lines.push('## 任务');
  lines.push('将3D导演台的人偶场景转化为真人影视级画面。每个人偶替换为对应的真人角色，严格保留原始场景的构图、光影和氛围。');
  lines.push('');
  lines.push('## 场景全貌');
  lines.push('图1是3D导演台的场景全貌截图，展示了所有角色的位置关系、场景布局、光照方向和整体氛围。生成的画面必须复刻图1的构图和光影。');
  lines.push('');

  lines.push('## 角色对应关系（严格一一对应，不要互换）');
  lines.push('');

  let imgIdx = 2;
  for (let ci = 0; ci < characterData.length; ci++) {
    const cd = characterData[ci];
    const colorName = hexToColorName(cd.stageCharColor);
    const poseIdx = imgIdx;
    const refIdx = imgIdx + 1;
    lines.push(
      `角色${ci + 1}「${cd.referenceCharName}」：` +
      `图${poseIdx}（${colorName}人偶）是该角色的3D姿态，` +
      `图${refIdx}是该角色的真人参考照。` +
      `生成时，该角色必须使用图${refIdx}的外貌/发型/服装，同时严格保持图${poseIdx}的姿势、朝向和在场景中的位置。`,
    );
    lines.push('');
    imgIdx += 2;
  }

  if (sceneDescription) {
    lines.push(`## 场景描述`);
    lines.push(sceneDescription);
    lines.push('');
  }

  lines.push('## 生成规则');
  lines.push('1. 每个角色的姿态、朝向、位置必须与其对应的3D姿态截图完全一致，不要互换角色');
  lines.push('2. 每个角色的外貌、发型、服装必须与其对应的真人参考照一致');
  lines.push('3. 整体构图、光影方向、色调氛围必须与图1（场景全貌）保持一致');
  lines.push('4. 角色身上的光影、色温必须与背景环境统一——光源方向、阴影角度、色调冷暖都要匹配场景，让角色自然融入背景，不能看起来像抠图贴上去的');
  lines.push('5. 画面品质：影视级，画面统一，不要改变原始光影');
  lines.push('6. 不要添加3D场景中没有的人物或元素');

  parts.push({ type: 'text', content: lines.join('\n') });

  return parts;
}

// ── Legacy prompt builder (kept for tests) ───────────────────────

/**
 * Build the Gemini prompt for multi-image character replacement.
 *
 * Image order convention:
 *   @1 = base scene screenshot
 *   @2 = char1 3D pose, @3 = char1 reference photo
 *   @4 = char2 3D pose, @5 = char2 reference photo
 *   ... and so on
 */
export function buildGeminiPrompt(
  mappings: CharacterMapping[],
  sceneDescription?: string,
): string {
  const lines: string[] = [];

  lines.push('请根据图片 @1 中的 3D 场景布局，生成一张影视级画面。');
  if (sceneDescription) {
    lines.push(`场景描述：${sceneDescription}`);
  }
  lines.push('');

  for (const m of mappings) {
    lines.push(
      `图片 @${m.poseImageIndex} 是"${m.referenceCharName}"的 3D 姿态截图（${m.stageCharColor}色人偶），` +
      `图片 @${m.refImageIndex} 是"${m.referenceCharName}"的参考形象。` +
      `请将该 3D 人偶替换为角色真实形象，保持完全一致的姿势和位置。`,
    );
  }

  lines.push('');
  lines.push('要求：');
  lines.push('1. 严格保持 3D 场景中每个角色的姿态、朝向和相对位置关系');
  lines.push('2. 每个角色的外貌、服装参照对应的参考图');
  lines.push('3. 画面风格统一，影视级品质，光影自然');
  lines.push('4. 背景保持 3D 场景中的环境，不要改变');

  return lines.join('\n');
}

// ── Image list builder ───────────────────────────────────────────

/**
 * Assemble the ordered image list for Gemini multi-image API.
 * Returns { data, index } pairs sorted by index.
 *
 * @param baseScreenshot  base64 of full scene
 * @param characterData   per-character: { poseScreenshot, referenceBase64 }
 * @returns sorted image list with @N indices
 */
export function buildImageList(
  baseScreenshot: string,
  characterData: Array<{ poseScreenshot: string; referenceBase64: string }>,
): Array<{ data: string; index: number }> {
  const images: Array<{ data: string; index: number }> = [];

  // @1 = base scene
  images.push({ data: baseScreenshot, index: 1 });

  // For each character: @N = 3D pose, @N+1 = reference photo
  let idx = 2;
  for (const cd of characterData) {
    images.push({ data: cd.poseScreenshot, index: idx++ });
    images.push({ data: cd.referenceBase64, index: idx++ });
  }

  return images;
}

/**
 * Build CharacterMapping array from screenshots + reference data.
 * Convenience function that computes the @N indices automatically.
 */
export function buildMappings(
  screenshots: StageScreenshots,
  references: Array<{ stageCharId: string; referenceCharName: string }>,
): CharacterMapping[] {
  const mappings: CharacterMapping[] = [];
  let idx = 2; // @1 is base scene

  for (const ref of references) {
    const charShot = screenshots.characters.find(c => c.stageCharId === ref.stageCharId);
    if (!charShot) continue;

    mappings.push({
      stageCharId: ref.stageCharId,
      stageCharName: charShot.stageCharName,
      stageCharColor: charShot.color,
      referenceCharName: ref.referenceCharName,
      poseImageIndex: idx,
      refImageIndex: idx + 1,
    });
    idx += 2;
  }

  return mappings;
}
