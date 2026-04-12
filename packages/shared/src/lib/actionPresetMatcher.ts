/**
 * Action keyword → body preset matcher.
 *
 * Maps Chinese action descriptions from shot data to POSE_PRESETS keys.
 * Used by DirectorStage3DNode to auto-select initial body preset
 * when characters are first placed on the 3D stage.
 */

/** Ordered matching rules — first match wins. More specific keywords come first. */
const ACTION_KEYWORD_MAP: Array<{ keywords: string[]; preset: string }> = [
  // Running (specific before generic)
  { keywords: ['奔跑', '飞奔', '狂奔', '冲刺'], preset: 'running' },
  { keywords: ['跑', '冲', '追'], preset: 'running' },
  // Walking
  { keywords: ['行走', '漫步', '踱步', '走来走去'], preset: 'walking' },
  { keywords: ['走近', '走向', '走过', '走到', '走'], preset: 'walking' },
  // Sitting
  { keywords: ['坐着', '坐下', '端坐', '坐在', '盘坐', '席地而坐'], preset: 'sitting' },
  // Crouching
  { keywords: ['蹲下', '蹲着', '蹲在'], preset: 'crouching' },
  // Lying down
  { keywords: ['躺着', '躺在', '躺下', '倒下', '瘫倒', '仰卧'], preset: 'lying' },
  // Prone
  { keywords: ['趴着', '趴在', '趴下', '俯卧', '匍匐'], preset: 'prone' },
  // Kneeling
  { keywords: ['跪下', '跪着', '跪在', '下跪', '跪地'], preset: 'kneeling' },
  // Hugging
  { keywords: ['搂', '拥抱', '抱住', '相拥', '依偎'], preset: 'hugging' },
  // Fighting
  { keywords: ['格斗', '搏斗', '打斗', '挥拳', '出拳', '拔剑'], preset: 'fighting' },
  // Thinking
  { keywords: ['思考', '沉思', '发呆', '凝视', '出神'], preset: 'thinking' },
  // Leaning
  { keywords: ['倚靠', '靠着', '靠在', '倚着', '倚门', '靠墙'], preset: 'leaning' },
  // Pointing
  { keywords: ['指着', '指向', '指了指', '伸手指'], preset: 'pointing' },
  // Bowing
  { keywords: ['鞠躬', '弯腰', '低头行礼', '欠身'], preset: 'bowing' },
  // Standing (generic fallback — placed last so specific actions match first)
  { keywords: ['站', '伫立', '站着', '站在', '立于'], preset: 'standing' },
];

/**
 * Match a Chinese action description to the best body preset key.
 * Returns 'standing' if no keywords match or action is empty.
 */
export function matchActionToPreset(action?: string): string {
  if (!action) return 'standing';
  for (const entry of ACTION_KEYWORD_MAP) {
    for (const kw of entry.keywords) {
      if (action.includes(kw)) return entry.preset;
    }
  }
  return 'standing';
}
