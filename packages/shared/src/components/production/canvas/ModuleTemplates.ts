// ══════════════════════════════════════════════════════════════
// ModuleTemplates.ts — 5 类场景工作流模块定义
//
// 用于 Agent 自动分类分镜场景类型，决定：
// - 使用哪个视频生成平台（可灵/即梦）
// - 应用哪种图片合成工作流步骤
// - 默认视频时长
//
// 与现有 ShotNode 配合使用：Shot 被分配 moduleType 后，
// 其下游 Image/Video 节点自动应用对应模块的参数模板。
// ══════════════════════════════════════════════════════════════

import type { CanvasModuleType, CanvasModuleTemplate } from '../../../types/canvas';

export const MODULE_TEMPLATES: Record<CanvasModuleType, CanvasModuleTemplate> = {
  dialogue: {
    type: 'dialogue',
    label: '对话场景',
    description: '适用于两人或多人对话、谈判、争论等场景',
    icon: '💬',
    color: '#378ADD',
    bgColor: 'rgba(59,138,221,0.06)',
    videoProvider: 'kling',
    defaultDuration: 5,
    detectionKeywords: [
      '说道', '回答', '问道', '回应', '对话', '争吵', '谈判',
      '低声', '大声', '沉默', '注视', '对视', '开口',
    ],
    steps: [
      { id: 'gen-bg', name: '生成对话背景', type: 'generate-background', description: '根据场景描述生成室内/室外背景', optional: false, defaultParams: { style: 'cinematic', lighting: 'natural', depth_of_field: true } },
      { id: 'gen-chars', name: '生成角色立绘', type: 'generate-character', description: '生成对话双方的角色图', optional: false, defaultParams: { pose: 'conversation', expression: 'neutral', angle: 'medium-shot' } },
      { id: 'remove-bg', name: '角色镂空', type: 'remove-background', description: '去除角色背景', optional: false, defaultParams: { method: 'ai-matting', edge_refine: true } },
      { id: 'composite', name: '图层合成', type: 'composite-layers', description: '将背景与角色合成', optional: false, defaultParams: { blend_mode: 'normal', shadow: true, color_match: true } },
    ],
  },

  action: {
    type: 'action',
    label: '打斗动作',
    description: '适用于战斗、追逐、激烈动作场景',
    icon: '⚔️',
    color: '#D85A30',
    bgColor: 'rgba(216,90,48,0.06)',
    videoProvider: 'jimeng',
    defaultDuration: 4,
    detectionKeywords: [
      '出拳', '踢击', '跳跃', '躲避', '攻击', '防御', '格挡',
      '追逐', '奔跑', '冲刺', '打斗', '战斗', '激战', '厮杀',
      '剑', '刀', '枪', '武器', '飞身', '翻滚',
    ],
    steps: [
      { id: 'gen-bg', name: '生成动作背景', type: 'generate-background', description: '生成适合打斗的背景', optional: false, defaultParams: { style: 'cinematic-action', lighting: 'dramatic', chaos_level: 0.4 } },
      { id: 'gen-chars', name: '生成动作角色帧', type: 'generate-character', description: '生成动作关键帧', optional: false, defaultParams: { pose: 'dynamic-action', motion_blur_hint: true } },
      { id: 'remove-bg', name: '角色镂空', type: 'remove-background', description: '精确镂空', optional: false, defaultParams: { method: 'ai-matting', edge_refine: true } },
      { id: 'add-props', name: '武器道具合成', type: 'add-props', description: '合入武器/道具', optional: true, defaultParams: { blend_shadow: true } },
      { id: 'motion-blur', name: '动态模糊', type: 'motion-blur', description: '施加方向性运动模糊', optional: true, defaultParams: { intensity: 0.5, direction: 'auto' } },
      { id: 'composite', name: '最终合成', type: 'composite-layers', description: '整合所有图层', optional: false, defaultParams: { contrast: 1.15, saturation: 1.1, vignette: true } },
    ],
  },

  suspense: {
    type: 'suspense',
    label: '悬疑揭秘',
    description: '适用于线索发现、真相揭露、惊悚氛围',
    icon: '🔍',
    color: '#534AB7',
    bgColor: 'rgba(83,74,183,0.06)',
    videoProvider: 'kling',
    defaultDuration: 6,
    detectionKeywords: [
      '发现', '线索', '真相', '秘密', '怀疑', '揭露', '惊讶',
      '恐惧', '不安', '阴暗', '谜团', '证据', '指纹', '血迹',
      '暗处', '潜伏', '跟踪', '窃听',
    ],
    steps: [
      { id: 'gen-bg', name: '生成悬疑背景', type: 'generate-background', description: '暗调有深度感的背景', optional: false, defaultParams: { style: 'noir', lighting: 'low-key', color_temp: 'cool' } },
      { id: 'gen-chars', name: '生成特写角色', type: 'generate-character', description: '表情特写', optional: false, defaultParams: { pose: 'close-up-expression', angle: 'close-up' } },
      { id: 'remove-bg', name: '角色镂空', type: 'remove-background', description: '精确镂空', optional: false, defaultParams: { method: 'ai-matting', edge_refine: true } },
      { id: 'apply-filter', name: '悬疑滤镜', type: 'apply-filter', description: '冷色调低饱和度滤镜', optional: false, defaultParams: { filter: 'suspense', desaturation: 0.3, shadow_crush: 0.2, grain: 0.15 } },
      { id: 'color-grade', name: '调色强化', type: 'color-grade', description: '高对比调色', optional: false, defaultParams: { focus_highlight: true, vignette_strength: 0.4 } },
    ],
  },

  landscape: {
    type: 'landscape',
    label: '环境转场',
    description: '适用于时间流逝、地点切换、场景过渡',
    icon: '🏔',
    color: '#1D9E75',
    bgColor: 'rgba(29,158,117,0.06)',
    videoProvider: 'jimeng',
    defaultDuration: 3,
    detectionKeywords: [
      '日出', '日落', '夜晚', '清晨', '黄昏', '转场', '场景切换',
      '远景', '全景', '航拍', '俯瞰', '大地', '天空', '云彩',
      '时光', '岁月', '季节', '流逝', '过去', '回忆',
    ],
    steps: [
      { id: 'gen-bg', name: '生成环境主图', type: 'generate-background', description: '环境全景图', optional: false, defaultParams: { style: 'cinematic-landscape', aspect_ratio: '16:9', atmospheric: true } },
      { id: 'adjust-lighting', name: '光线时间调整', type: 'adjust-lighting', description: '按剧情时间调整光线', optional: false, defaultParams: { time_of_day: 'auto', sky_replace: true } },
      { id: 'color-grade', name: '氛围调色', type: 'color-grade', description: '配合情绪调色', optional: false, defaultParams: { mood: 'auto', lut_preset: 'cinematic' } },
    ],
  },

  emotion: {
    type: 'emotion',
    label: '情感内心',
    description: '适用于内心独白、回忆闪回、梦境、情绪爆发',
    icon: '💭',
    color: '#D4537E',
    bgColor: 'rgba(212,83,126,0.06)',
    videoProvider: 'kling',
    defaultDuration: 6,
    detectionKeywords: [
      '想起', '回忆', '心中', '内心', '感受', '情绪', '泪水',
      '悲伤', '喜悦', '愤怒', '绝望', '希望', '梦境', '幻觉',
      '独白', '思绪', '感动', '震撼', '心碎',
    ],
    steps: [
      { id: 'gen-bg', name: '生成情感背景', type: 'generate-background', description: '梦幻/虚化背景', optional: false, defaultParams: { style: 'emotional-dreamlike', bokeh: true, abstraction: 0.3 } },
      { id: 'gen-chars', name: '生成情感角色', type: 'generate-character', description: '面部表情刻画', optional: false, defaultParams: { pose: 'emotional-portrait', angle: 'close-up', expression_intensity: 0.8 } },
      { id: 'remove-bg', name: '角色镂空', type: 'remove-background', description: '软边缘镂空', optional: false, defaultParams: { method: 'ai-matting', edge_refine: true } },
      { id: 'apply-filter', name: '情感滤镜', type: 'apply-filter', description: '柔焦滤镜', optional: false, defaultParams: { filter: 'emotional', soft_focus: 0.2, halation: 0.1 } },
      { id: 'color-grade', name: '情感调色', type: 'color-grade', description: '强化情感色彩', optional: false, defaultParams: { emotion_driven: true } },
    ],
  },
};

/** 根据分镜文本关键词快速识别模块类型（精确识别由 Agent 完成） */
export function detectModuleType(text: string): CanvasModuleType | null {
  const scores: Record<CanvasModuleType, number> = {
    dialogue: 0, action: 0, suspense: 0, landscape: 0, emotion: 0,
  };
  for (const [type, template] of Object.entries(MODULE_TEMPLATES)) {
    for (const keyword of template.detectionKeywords) {
      if (text.includes(keyword)) scores[type as CanvasModuleType]++;
    }
  }
  const maxScore = Math.max(...Object.values(scores));
  if (maxScore === 0) return null;
  return Object.entries(scores).find(([, score]) => score === maxScore)?.[0] as CanvasModuleType;
}
