// ══════════════════════════════════════════════════════════════
// ModuleTemplates.ts — 5 类工作流模块定义
// ══════════════════════════════════════════════════════════════

import type {
  CanvasModuleType,
  CanvasModuleTemplate,
  CanvasVideoProvider,
} from '../../types/canvas';

export const MODULE_TEMPLATES: Record<CanvasModuleType, CanvasModuleTemplate> = {
  // ── 对话场景 ──
  dialogue: {
    type: 'dialogue',
    label: '对话场景',
    description: '适用于两人或多人对话、谈判、争论等场景',
    icon: '💬',
    color: '#378ADD',
    bgColor: 'rgba(59,138,221,0.06)',
    videoProvider: 'kling' as CanvasVideoProvider,
    defaultDuration: 5,
    detectionKeywords: [
      '说道', '回答', '问道', '回应', '对话', '争吵', '谈判',
      '低声', '大声', '沉默', '注视', '对视', '开口',
    ],
    steps: [
      {
        id: 'gen-bg', name: '生成对话背景', type: 'generate-background',
        description: '根据场景描述生成室内/室外背景', optional: false,
        defaultParams: { style: 'cinematic', lighting: 'natural', depth_of_field: true },
      },
      {
        id: 'gen-chars', name: '生成角色立绘', type: 'generate-character',
        description: '生成对话双方的角色图（使用资产库角色参考）', optional: false,
        defaultParams: { pose: 'conversation', expression: 'neutral', angle: 'medium-shot' },
      },
      {
        id: 'remove-bg', name: '角色镂空', type: 'remove-background',
        description: '去除角色背景，保留透明通道', optional: false,
        defaultParams: { method: 'ai-matting', edge_refine: true },
      },
      {
        id: 'composite', name: '图层合成', type: 'composite-layers',
        description: '将背景与角色合成，调整位置/比例/光线匹配', optional: false,
        defaultParams: { blend_mode: 'normal', shadow: true, color_match: true },
      },
    ],
  },

  // ── 打斗动作 ──
  action: {
    type: 'action',
    label: '打斗动作',
    description: '适用于战斗、追逐、激烈动作场景',
    icon: '⚔️',
    color: '#D85A30',
    bgColor: 'rgba(216,90,48,0.06)',
    videoProvider: 'jimeng' as CanvasVideoProvider,
    defaultDuration: 4,
    detectionKeywords: [
      '出拳', '踢击', '跳跃', '躲避', '攻击', '防御', '格挡',
      '追逐', '奔跑', '冲刺', '打斗', '战斗', '激战', '厮杀',
      '剑', '刀', '枪', '武器', '飞身', '翻滚',
    ],
    steps: [
      {
        id: 'gen-bg', name: '生成动作背景', type: 'generate-background',
        description: '生成适合打斗的背景（广阔空间/废墟/街道）', optional: false,
        defaultParams: { style: 'cinematic-action', lighting: 'dramatic', chaos_level: 0.4 },
      },
      {
        id: 'gen-chars', name: '生成动作角色帧', type: 'generate-character',
        description: '生成动作关键帧（攻击/防御/飞跃姿态）', optional: false,
        defaultParams: { pose: 'dynamic-action', motion_blur_hint: true, multiple_frames: true },
      },
      {
        id: 'remove-bg', name: '角色镂空', type: 'remove-background',
        description: '精确镂空动作角色', optional: false,
        defaultParams: { method: 'ai-matting', edge_refine: true },
      },
      {
        id: 'add-props', name: '武器道具合成', type: 'add-props',
        description: '从资产库调取武器/道具并合入画面', optional: true,
        defaultParams: { blend_shadow: true },
      },
      {
        id: 'motion-blur', name: '动态模糊处理', type: 'motion-blur',
        description: '对动作部分施加方向性运动模糊', optional: true,
        defaultParams: { intensity: 0.5, direction: 'auto' },
      },
      {
        id: 'composite', name: '最终合成', type: 'composite-layers',
        description: '整合所有图层，增强对比度与饱和度', optional: false,
        defaultParams: { contrast: 1.15, saturation: 1.1, vignette: true },
      },
    ],
  },

  // ── 悬疑揭秘 ──
  suspense: {
    type: 'suspense',
    label: '悬疑揭秘',
    description: '适用于线索发现、真相揭露、惊悚氛围场景',
    icon: '🔍',
    color: '#534AB7',
    bgColor: 'rgba(83,74,183,0.06)',
    videoProvider: 'kling' as CanvasVideoProvider,
    defaultDuration: 6,
    detectionKeywords: [
      '发现', '线索', '真相', '秘密', '怀疑', '揭露', '惊讶',
      '恐惧', '不安', '阴暗', '谜团', '证据', '指纹', '血迹',
      '暗处', '潜伏', '跟踪', '窃听',
    ],
    steps: [
      {
        id: 'gen-bg', name: '生成悬疑背景', type: 'generate-background',
        description: '生成暗调、有深度感的场景背景', optional: false,
        defaultParams: { style: 'noir', lighting: 'low-key', color_temp: 'cool' },
      },
      {
        id: 'gen-chars', name: '生成特写角色', type: 'generate-character',
        description: '生成表情特写（震惊/恐惧/疑惑）', optional: false,
        defaultParams: { pose: 'close-up-expression', angle: 'close-up' },
      },
      {
        id: 'remove-bg', name: '角色镂空', type: 'remove-background',
        description: '精确镂空角色', optional: false,
        defaultParams: { method: 'ai-matting', edge_refine: true },
      },
      {
        id: 'apply-filter', name: '悬疑滤镜', type: 'apply-filter',
        description: '添加冷色调、低饱和度、阴影压重滤镜', optional: false,
        defaultParams: { filter: 'suspense', desaturation: 0.3, shadow_crush: 0.2, grain: 0.15 },
      },
      {
        id: 'color-grade', name: '调色强化', type: 'color-grade',
        description: '高对比调色，突出线索/道具的焦点区域', optional: false,
        defaultParams: { focus_highlight: true, vignette_strength: 0.4 },
      },
    ],
  },

  // ── 环境转场 ──
  landscape: {
    type: 'landscape',
    label: '环境转场',
    description: '适用于时间流逝、地点切换、场景过渡',
    icon: '🏔',
    color: '#1D9E75',
    bgColor: 'rgba(29,158,117,0.06)',
    videoProvider: 'jimeng' as CanvasVideoProvider,
    defaultDuration: 3,
    detectionKeywords: [
      '日出', '日落', '夜晚', '清晨', '黄昏', '转场', '场景切换',
      '远景', '全景', '航拍', '俯瞰', '大地', '天空', '云彩',
      '时光', '岁月', '季节', '流逝', '过去', '回忆',
    ],
    steps: [
      {
        id: 'gen-bg', name: '生成环境主图', type: 'generate-background',
        description: '生成环境全景图，带时间/天气信息', optional: false,
        defaultParams: { style: 'cinematic-landscape', aspect_ratio: '16:9', atmospheric: true },
      },
      {
        id: 'adjust-lighting', name: '光线时间调整', type: 'adjust-lighting',
        description: '按剧情时间调整光线：晨/昼/暮/夜', optional: false,
        defaultParams: { time_of_day: 'auto', sky_replace: true },
      },
      {
        id: 'color-grade', name: '氛围调色', type: 'color-grade',
        description: '配合剧情情绪调色（温暖/冷峻/压抑/明快）', optional: false,
        defaultParams: { mood: 'auto', lut_preset: 'cinematic' },
      },
    ],
  },

  // ── 情感内心 ──
  emotion: {
    type: 'emotion',
    label: '情感内心',
    description: '适用于内心独白、回忆闪回、梦境、情绪爆发',
    icon: '💭',
    color: '#D4537E',
    bgColor: 'rgba(212,83,126,0.06)',
    videoProvider: 'kling' as CanvasVideoProvider,
    defaultDuration: 6,
    detectionKeywords: [
      '想起', '回忆', '心中', '内心', '感受', '情绪', '泪水',
      '悲伤', '喜悦', '愤怒', '绝望', '希望', '梦境', '幻觉',
      '独白', '思绪', '感动', '震撼', '心碎',
    ],
    steps: [
      {
        id: 'gen-bg', name: '生成情感背景', type: 'generate-background',
        description: '生成梦幻/虚化/象征性背景', optional: false,
        defaultParams: { style: 'emotional-dreamlike', bokeh: true, abstraction: 0.3 },
      },
      {
        id: 'gen-chars', name: '生成情感角色', type: 'generate-character',
        description: '重点刻画面部表情，体现情绪核心', optional: false,
        defaultParams: { pose: 'emotional-portrait', angle: 'close-up', expression_intensity: 0.8 },
      },
      {
        id: 'remove-bg', name: '角色镂空', type: 'remove-background',
        description: '软边缘镂空，与梦幻背景融合', optional: false,
        defaultParams: { method: 'ai-matting', edge_refine: true },
      },
      {
        id: 'apply-filter', name: '情感滤镜', type: 'apply-filter',
        description: '柔焦/暖色/冷色/黑白滤镜，配合情绪', optional: false,
        defaultParams: { filter: 'emotional', soft_focus: 0.2, halation: 0.1 },
      },
      {
        id: 'color-grade', name: '情感调色', type: 'color-grade',
        description: '强化情感色彩（红-愤怒/蓝-悲伤/金-温暖）', optional: false,
        defaultParams: { emotion_driven: true },
      },
    ],
  },
};

/** 根据分镜文本的关键词匹配，快速识别模块类型（精确识别由 Agent 完成） */
export function detectModuleType(text: string): CanvasModuleType | null {
  const scores: Record<CanvasModuleType, number> = {
    dialogue: 0, action: 0, suspense: 0, landscape: 0, emotion: 0,
  };

  for (const [type, template] of Object.entries(MODULE_TEMPLATES)) {
    for (const keyword of template.detectionKeywords) {
      if (text.includes(keyword)) {
        scores[type as CanvasModuleType]++;
      }
    }
  }

  const maxScore = Math.max(...Object.values(scores));
  if (maxScore === 0) return null;
  return Object.entries(scores).find(([, score]) => score === maxScore)?.[0] as CanvasModuleType;
}
