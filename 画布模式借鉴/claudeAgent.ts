// ============================================================
// claudeAgent.ts - Claude claude-opus-4-6 Agent服务
// 这是与现有软件体系的核心接入点
// ============================================================
import Anthropic from '@anthropic-ai/sdk';
import { NodeData, ProjectAsset, StoryboardContent, ModuleType } from '../types';
import { MODULE_TEMPLATES } from '../components/Modules/ModuleTemplates';

// Claude claude-opus-4-6 接入配置
const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.REACT_APP_ANTHROPIC_API_KEY,
  // 如果是通过自己的后端代理：
  // baseURL: process.env.CLAUDE_API_BASE_URL,
});

const MODEL = 'claude-opus-4-6'; // 指定使用 claude-opus-4-6

// ============================================================
// 1. 分镜分析：从分镜文本生成图片提示词 & 视频提示词
// ============================================================
interface AnalyzeOptions {
  assets: ProjectAsset[];
  onProgress?: (partial: Partial<StoryboardContent>) => void;
  onComplete?: () => void;
}

async function analyzeStoryboard(node: NodeData, options: AnalyzeOptions): Promise<void> {
  const content = node.content as StoryboardContent;
  const { assets, onProgress, onComplete } = options;

  const characters = assets.filter(a => a.type === 'character' && content.characterIds.includes(a.id));
  const sceneAsset = assets.find(a => a.type === 'scene' && a.id === content.sceneAssetId);

  const systemPrompt = `你是专业的影视分镜师和AI绘图提示词专家，负责将小说分镜文本转化为精准的AI生图提示词和视频提示词。

工作规则：
1. 图片提示词(imagePrompt)：用英文写，描述静态画面构图，包含：镜头类型、角色位置/表情/姿态、场景光线/氛围、风格关键词（写实电影质感）
2. 视频提示词(videoPrompt)：用中文写，描述画面运动方式，包含：镜头运动（推/拉/摇/跟）、角色动作、时长建议、节奏感
3. 严格使用资产库中已有的角色外貌描述，保持一致性
4. 输出必须是JSON格式，不要有任何多余文字

输出JSON格式：
{
  "imagePrompt": "英文图片提示词",
  "videoPrompt": "中文视频提示词",
  "shotType": "close-up|medium|wide|overhead|low-angle|pov|over-shoulder",
  "emotion": "情绪关键词（如：紧张、温馨、悲伤）",
  "duration": 时长秒数
}`;

  const userPrompt = `分析以下分镜并生成提示词：

【分镜文本】
${content.rawText}

【场景信息】
${sceneAsset ? `场景：${sceneAsset.name} - ${sceneAsset.description}` : '场景：未指定'}
时间：${content.emotion || '日间'}

【角色信息】
${characters.length > 0
  ? characters.map(c => `- ${c.name}: ${c.description}，外貌特征：${c.tags.join('、')}`).join('\n')
  : '无角色'
}

【已知情绪基调】
${content.emotion || '待分析'}

请生成精准的提示词，确保与资产库中的角色外貌保持一致。`;

  // 使用流式输出
  let fullText = '';
  const stream = await client.messages.stream({
    model: MODEL,
    max_tokens: 1000,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  });

  for await (const chunk of stream) {
    if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
      fullText += chunk.delta.text;
    }
  }

  // 解析JSON
  try {
    const cleaned = fullText.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    const parsed = JSON.parse(cleaned);
    onProgress?.({
      imagePrompt: parsed.imagePrompt,
      videoPrompt: parsed.videoPrompt,
      shotType: parsed.shotType,
      emotion: parsed.emotion,
      duration: parsed.duration || 5,
    });
    onComplete?.();
  } catch (e) {
    console.error('Failed to parse Claude response:', e, fullText);
    throw new Error('Claude响应解析失败');
  }
}


// ============================================================
// 2. 批量模块分配：分析多个分镜，确定各自最适合的工作流模块
// ============================================================
async function batchAssignModules(
  nodes: NodeData[]
): Promise<Array<{ nodeId: string; moduleType: ModuleType; confidence: number }>> {

  const moduleDescriptions = Object.entries(MODULE_TEMPLATES).map(([type, tmpl]) => ({
    type,
    label: tmpl.label,
    description: tmpl.description,
    keywords: tmpl.detectionKeywords.slice(0, 8).join('、'),
  }));

  const systemPrompt = `你是专业的影视制作编导，负责将小说分镜按场景类型分类，以便应用不同的视频制作工作流。

可用的工作流模块：
${moduleDescriptions.map(m => `- ${m.type}（${m.label}）：${m.description}，关键词：${m.keywords}`).join('\n')}

分类规则：
1. 根据分镜的核心内容和情绪，选择最匹配的模块类型
2. 每个分镜只能分配一个模块
3. 如果一个分镜同时包含对话和打斗，以占比更高的为准
4. 环境转场模块仅用于无角色的纯景别镜头

输出严格按JSON格式，不含任何解释文字：
[{"nodeId": "xxx", "moduleType": "dialogue|action|suspense|landscape|emotion", "confidence": 0.0-1.0}]`;

  const userContent = nodes.map(n => {
    const content = n.content as StoryboardContent;
    return `{"nodeId": "${n.id}", "text": "${(content.rawText || '').slice(0, 150)}"}`;
  }).join('\n');

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 2000,
    system: systemPrompt,
    messages: [{
      role: 'user',
      content: `请对以下分镜进行模块分类：\n${userContent}`,
    }],
  });

  const text = response.content.map(b => b.type === 'text' ? b.text : '').join('');
  const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

  try {
    return JSON.parse(cleaned);
  } catch {
    // 如果解析失败，返回默认分配
    return nodes.map(n => ({ nodeId: n.id, moduleType: 'dialogue' as ModuleType, confidence: 0.5 }));
  }
}


// ============================================================
// 3. 提示词优化：对已有提示词进行质量提升
// ============================================================
async function optimizePrompt(
  type: 'image' | 'video',
  currentPrompt: string,
  context: {
    rawText: string;
    emotion: string;
    moduleType: ModuleType;
    shotType: string;
  }
): Promise<string> {

  const moduleInfo = MODULE_TEMPLATES[context.moduleType];

  const systemPrompt = type === 'image'
    ? `你是AI绘图提示词优化专家。请优化给定的英文图片提示词，使其更精准、更具电影质感。
要求：
1. 保持原有核心内容，不改变场景意图
2. 增强视觉细节描述（光线、质感、色调）
3. 加入电影摄影相关术语
4. 适应${moduleInfo.label}的视觉风格：${moduleInfo.description}
5. 输出只包含优化后的提示词，不含解释`
    : `你是视频生成提示词优化专家。请优化给定的中文视频提示词，使镜头运动更专业。
要求：
1. 明确镜头运动方式（推/拉/摇/跟/固定/手持）
2. 描述运动的速度和节奏
3. 适应${moduleInfo.label}的氛围
4. 输出只包含优化后的提示词，不含解释`;

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 500,
    system: systemPrompt,
    messages: [{
      role: 'user',
      content: `原始分镜：${context.rawText}\n情绪：${context.emotion}\n当前提示词：${currentPrompt}\n\n请优化：`,
    }],
  });

  return response.content.map(b => b.type === 'text' ? b.text : '').join('').trim();
}


// ============================================================
// 4. 审查图片构图：给合成图提供修改建议
// ============================================================
async function reviewComposition(
  imageBase64: string,
  storyboardText: string,
  moduleType: ModuleType
): Promise<{ score: number; suggestions: string[] }> {

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 800,
    messages: [{
      role: 'user',
      content: [
        {
          type: 'image',
          source: {
            type: 'base64',
            media_type: 'image/jpeg',
            data: imageBase64,
          },
        },
        {
          type: 'text',
          text: `请审查这张合成图是否符合以下分镜要求：

分镜内容：${storyboardText}
场景模块：${MODULE_TEMPLATES[moduleType].label}

请从以下维度评分并给出具体修改建议（JSON格式）：
{
  "score": 0-10,
  "suggestions": ["建议1", "建议2"]
}

评分维度：构图合理性、角色位置、光线匹配、情绪传达`,
        },
      ],
    }],
  });

  const text = response.content.map(b => b.type === 'text' ? b.text : '').join('');
  try {
    const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
    return JSON.parse(cleaned);
  } catch {
    return { score: 7, suggestions: ['无法解析评审结果'] };
  }
}


// ============================================================
// 5. 整章批量分析（分析整章的分镜链，提前生成所有提示词）
// ============================================================
async function analyzeChapter(
  chapterId: string,
  nodes: NodeData[],
  assets: ProjectAsset[]
): Promise<void> {
  // 按顺序处理，避免并发过多
  for (const node of nodes) {
    if (node.type === 'storyboard') {
      await analyzeStoryboard(node, { assets });
      // 延迟避免限流
      await new Promise(resolve => setTimeout(resolve, 200));
    }
  }
}


// ============================================================
// 导出
// ============================================================
export const claudeAgent = {
  analyzeStoryboard,
  batchAssignModules,
  optimizePrompt,
  reviewComposition,
  analyzeChapter,
};
