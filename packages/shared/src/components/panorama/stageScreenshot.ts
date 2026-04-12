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
    /** Bounding box as percentage of 1920×1080 frame (0–100) */
    bbox?: { left: number; top: number; width: number; height: number };
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
    bbox?: { left: number; top: number; width: number; height: number };
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
  lines.push('将3D导演台的人偶场景转化为高品质影视级画面。每个彩色人偶替换为其对应的角色参考照中的人物形象。严格保留原始场景的构图、光影和氛围。');
  lines.push('');
  lines.push('## 场景全貌（图1）');
  lines.push('图1是3D导演台的场景全貌截图。生成的画面必须在以下三个维度同时精确复刻图1：');
  lines.push('1. **构图复刻**：每个人偶在画面中的位置（左/中/右、上/中/下）、占画面的面积比例、身体朝向和角度——生成的角色必须与人偶完全一致，不能移动、不能放大缩小、不能改变朝向');
  lines.push('2. **姿态复刻**：每个人偶的身体姿势（站/坐/蹲等）、肢体动作（手臂抬起/下垂、腿弯曲/伸直）、身体倾斜角度和转向——角色必须精确还原');
  lines.push('3. **光影复刻**：图1中的光源位置、光照强度、色温和整体亮度——角色必须被同样的光源照亮，亮度和色温与周围环境一致');
  lines.push('');

  lines.push('## 角色对应关系（严格一一对应，不要互换）');
  lines.push('');

  let imgIdx = 2;
  for (let ci = 0; ci < characterData.length; ci++) {
    const cd = characterData[ci];
    const colorName = hexToColorName(cd.stageCharColor);
    const poseIdx = imgIdx;
    const refIdx = imgIdx + 1;

    // Build position description from bbox
    let posDesc = '';
    if (cd.bbox) {
      const centerX = cd.bbox.left + cd.bbox.width / 2;
      const centerY = cd.bbox.top + cd.bbox.height / 2;
      const hPos = centerX < 33 ? '画面左侧' : centerX < 66 ? '画面中部' : '画面右侧';
      const vPos = centerY < 33 ? '上方' : centerY < 66 ? '中间' : '下方';
      const right = +(cd.bbox.left + cd.bbox.width).toFixed(1);
      const bottom = +(cd.bbox.top + cd.bbox.height).toFixed(1);
      posDesc = `【位置锁定】该角色在图1中位于${hPos}${vPos}，精确坐标：左边界${cd.bbox.left}%、上边界${cd.bbox.top}%、右边界${right}%、下边界${bottom}%，宽${cd.bbox.width}%×高${cd.bbox.height}%。生成后角色的轮廓必须落在这个矩形区域内，不能偏移也不能放大缩小。`;
    }

    lines.push(
      `角色${ci + 1}「${cd.referenceCharName}」：` +
      `图${poseIdx}（${colorName}人偶）是该角色的3D姿态截图。` +
      `图${refIdx}是该角色的参考形象照。` +
      (posDesc ? posDesc : '') +
      `生成时：` +
      `(a) 【姿态精确复刻】角色的身体姿势、肢体动作、身体朝向和倾斜角度必须与图${poseIdx}中人偶完全一致——如果人偶身体向左侧转了30°，角色也必须向左侧转30°，绝对不能变成正面朝前；如果人偶微微前倾，角色也必须微微前倾。仔细观察人偶的：躯干朝向、头部转向、手臂姿态、腿部弯曲角度；` +
      `(b) 【位置精确复刻】角色在画面中的水平位置和垂直位置必须与图${poseIdx}中人偶完全一致——如果人偶偏左站立，角色也必须偏左站立，绝对不能移到画面中央；` +
      `(c) 角色的面容、脸型、五官、发型、发饰、服装必须与图${refIdx}高度一致，保持图${refIdx}的艺术风格（CG风保持CG风，不要转为写实风）；` +
      `(d) 参考照的光照条件必须丢弃，角色必须被场景实际光源照亮，亮度和色温与周围环境一致。`,
    );
    lines.push('');
    imgIdx += 2;
  }

  if (sceneDescription) {
    lines.push(`## 场景描述`);
    lines.push(sceneDescription);
    lines.push('');
  }

  lines.push('## 生成规则（按优先级排序，必须全部严格遵守）');
  lines.push('1. **位置锁定**：每个角色在画面中的位置必须与图1中对应人偶完全一致。如果人偶在画面左侧1/3处，角色就必须在左侧1/3处——绝对禁止将角色向画面中央偏移或重新居中。上方给出了每个角色的精确百分比坐标矩形，角色轮廓必须落在该矩形内');
  lines.push('2. **朝向锁定**：每个角色的身体朝向、躯干转向角度、头部转向必须与其3D姿态截图中的人偶完全一致。如果人偶身体侧转、斜对镜头，角色也必须侧转、斜对镜头——绝对禁止将角色转为正面朝前的对称站姿');
  lines.push('3. **姿势锁定**：每个角色的身体姿势（坐/站/蹲/躺等）、肢体动作（手臂高低、腿部弯曲）、身体倾斜角度必须与其3D姿态截图完全一致');
  lines.push('4. **大小锁定**：每个角色在画面中占据的面积比例必须与图1中对应人偶完全一致——不能放大也不能缩小，头顶和脚底必须与人偶对齐');
  lines.push('5. **环境光融合**：角色不能看起来像贴图。必须：(a)丢弃参考照的棚拍光照；(b)角色亮度≈环境亮度（暗场景中角色也必须暗）；(c)角色色温与背景一致（烛光→暖黄，月光→冷蓝）；(d)角色身上有与光源方向一致的明暗面；(e)角色脚下/身下有投射阴影；(f)轮廓边缘自然过渡');
  lines.push('6. **面部一致性**：脸型、五官必须与参考照高度一致。肤色基调保持一致但明暗和色温适配场景光照');
  lines.push('7. **风格保真**：角色艺术风格与参考照一致（CG风保持CG风，不要转为写实风）');
  lines.push('8. 发型、发饰、服装款式和颜色与参考照完全一致');
  lines.push('9. 画面品质：影视级品质，画面统一');
  lines.push('10. 不要添加3D场景中没有的人物或元素');

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
