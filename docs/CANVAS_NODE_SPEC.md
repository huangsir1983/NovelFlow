# 影视创作画布节点规格书

> 版本 1.0
> 日期 2026-03-06
> 关联文档 docs/CANVAS_SYSTEM_DESIGN.md

---

## 1. 文档目的

本文档定义影视创作画布在 Phase 1 和后续阶段的节点规格标准 用于统一前端节点 UI 后端执行器 数据回写和测试验收口径。

适用范围包括：

- 节点命名规范
- 节点输入输出规范
- 节点配置字段规范
- 节点状态与错误态规范
- 节点回写规则
- Phase 1 节点详细定义

---

## 2. 通用节点规格

### 2.1 节点分类

- 输入节点 接收用户原始输入或外部参考
- 分析节点 将原始材料结构化
- 创作节点 生成 Beat Scene Dialogue 等中间结果
- 导演节点 生成 Shot 与镜头语言
- 视觉节点 生成角色卡 风格板 Prompt 等视觉资产
- 生成节点 调用图像 视频 音频模型
- 输出节点 生成 Animatic 字幕 Draft 等交付结果
- 控制节点 控制分支 审批 汇合 并行执行

### 2.2 节点统一状态

- `idle` 未运行
- `queued` 已进入队列
- `running` 正在执行
- `success` 成功完成
- `warning` 完成但存在警告
- `error` 执行失败
- `blocked` 由于上游失败或输入不满足而阻塞

### 2.3 通用字段

```ts
interface BaseNodeSpec {
  type: string;
  title: string;
  group: 'input' | 'analysis' | 'creative' | 'director' | 'visual' | 'generation' | 'output' | 'control';
  editionRequired: 'normal' | 'canvas' | 'hidden' | 'ultimate';
  inputPorts: Array{ name: string; schema: string; required: boolean }>;
  outputPorts: Array{ name: string; schema: string }>;
  configSchema: Record<string, unknown>;
  canRunIndependently: boolean;
  canWriteBack: boolean;
  defaultSize: { width: number; height: number };
}
```

### 2.4 节点结果卡统一内容

每个节点的结果卡至少包含以下区域：

- 标题与状态
- 运行耗时与成本
- 结果摘要
- 预览区域
- 错误或警告区域
- 操作按钮 查看详情 重跑 回写 继续下游

### 2.5 错误态规范

- 输入缺失 标记为 `blocked` 并提示缺少上游输出
- 模型调用失败 标记为 `error` 并记录 provider code message
- 结果不合法 标记为 `warning` 或 `error` 视严重程度而定
- 回写失败 标记为 `warning` 但保留节点结果工件 允许重试回写

### 2.6 回写原则

- 节点结果应先保存为工件 再回写业务实体
- 回写必须可重试 可审计
- 回写动作必须显式显示给用户 不能悄悄覆盖用户修改 

---

## 3. Phase 1 节点详细定义

### 3.1 `NovelImportNode` 小说导入节点

- 分组 输入节点
- 适用版本 normal 及以上
- 作用 接收 txt md docx 等小说内容并生成标准文档对象
- 输入端口 无
- 输出端口 `raw_document` `source_meta`
- 核心配置 `fileType` `encoding` `language`
- 可独立运行 是
- 可回写 是 回写 `SourceDocument`
- 验收标准 可创建文档记录 返回文档摘要和字数统计

### 3.2 `ScriptImportNode` 剧本导入节点

- 分组 输入节点
- 适用版本 canvas 及以上
- 作用 接收 fountain fdx txt docx 剧本并标准化为内部结构
- 输入端口 无
- 输出端口 `raw_script` `script_meta`
- 核心配置 `formatHint` `language`
- 可独立运行 是
- 可回写 是 回写 `SourceDocument`
- 验收标准 输出场景列表基础骨架或标准剧本文本

### 3.3 `NormalizeTextNode` 文本标准化节点

- 分组 分析节点
- 作用 清洗换行 章节标题 杂质字符 并统一段落结构
- 输入端口 `raw_document` 或 `raw_script`
- 输出端口 `normalized_text`
- 核心配置 `stripAds` `normalizePunctuation` `keepChapterMarkers`
- 可独立运行 否 依赖输入节点
- 可回写 否 仅保存工件
- 验收标准 文本清洗后可稳定进入切分和提取节点

### 3.4 `ChapterSplitNode` 章节切分节点

- 分组 分析节点
- 作用 把长文本切分为章节或片段单元
- 输入端口 `normalized_text`
- 输出端口 `chapters`
- 核心配置 `strategy` `maxTokensPerChunk` `mergeShortSegments`
- 可回写 是 回写 `Chapter[]`
- 验收标准 返回章节序列 标题 序号 字数和摘要

### 3.5 `CharacterExtractNode` 角色提取节点

- 分组 分析节点
- 作用 抽取角色名称 别名 身份 关系和初步画像
- 输入端口 `normalized_text` `chapters`
- 输出端口 `characters`
- 核心配置 `includeAliases` `inferRelations` `extractGoals`
- 可回写 是 回写 `Character[]`
- 验收标准 输出角色列表 角色关系和置信度

### 3.6 `LocationExtractNode` 场景提取节点

- 分组 分析节点
- 作用 抽取地点 场景属性 时间段和环境标签
- 输入端口 `normalized_text` `chapters`
- 输出端口 `locations`
- 核心配置 `mergeDuplicates` `inferTimeOfDay`
- 可回写 是 回写 `Location[]`
- 验收标准 输出场景档案及可复用标签

### 3.7 `StoryBibleNode` 故事圣经节点

- 分组 分析节点
- 作用 汇总角色 场景 世界观和主题信息 生成 Story Bible
- 输入端口 `characters` `locations` `normalized_text`
- 输出端口 `story_bible`
- 核心配置 `includeTheme` `includeWorldRules` `includeConflicts`
- 可回写 是 回写 `StoryBible`
- 验收标准 生成项目级故事概要 世界规则和人物关系摘要 

### 3.8 `BeatGenerateNode` Beat 生成节点

- 分组 创作节点
- 作用 基于 Story Bible 和章节内容生成 Beat 列表
- 输入端口 `story_bible` `chapters`
- 输出端口 `beats`
- 核心配置 `beatDensity` `genrePreset` `microDramaMode`
- 可回写 是 回写 `Beat[]`
- 验收标准 输出顺序化 Beat 包含目标 冲突 转折 情绪峰值

### 3.9 `SceneGenerateNode` Scene 生成节点

- 分组 创作节点
- 作用 把 Beat 转换为结构化 Scene 列表
- 输入端口 `beats` `story_bible`
- 输出端口 `scenes`
- 核心配置 `sceneLength` `dialogueRatio` `visualDensity`
- 可回写 是 回写 `Scene[]`
- 验收标准 Scene 包含场景名 目标 角色 时空和摘要

### 3.10 `ConsistencyReviewNode` 一致性审查节点

- 分组 控制与审查节点
- 作用 检查角色命名 场景逻辑 基础事实和时空冲突
- 输入端口 `story_bible` `beats` `scenes`
- 输出端口 `review_report`
- 核心配置 `strictness` `autoFixMinorIssues`
- 可回写 是 回写 `Review[]`
- 验收标准 输出问题列表 严重度和建议修复动作

### 3.11 `ShotGenerateNode` Shot 生成节点

- 分组 导演节点
- 作用 把 Scene 拆解为 Shot 列表
- 输入端口 `scenes` `story_bible`
- 输出端口 `shots`
- 核心配置 `granularity` `coverageMode` `platformPreset`
- 可回写 是 回写 `Shot[]`
- 验收标准 生成镜头序列并包含时长与基础机位建议

### 3.12 `VisualPromptNode` 视觉 Prompt 节点

- 分组 视觉节点
- 作用 基于 Shot 和角色风格生成图像生成 Prompt
- 输入端口 `shots` `story_bible`
- 输出端口 `visual_prompts`
- 核心配置 `stylePreset` `cameraLanguage` `anchorAssets`
- 可回写 是 回写 `PromptAsset[]` 或 `Shot.prompt`
- 验收标准 每个 Shot 均可得到可预览的视觉 Prompt

### 3.13 `ImageGenNode` 图像生成节点

- 分组 生成节点
- 作用 为 Shot 批量生成静帧预览
- 输入端口 `visual_prompts`
- 输出端口 `images`
- 核心配置 `provider` `resolution` `candidates` `seed`
- 可回写 是 回写 `MediaAsset[]`
- 验收标准 支持单镜头重跑和结果回填

### 3.14 `TTSNode` 配音占位节点

- 分组 生成节点
- 作用 生成旁白或对白占位音轨
- 输入端口 `scenes` 或 `shots`
- 输出端口 `audio_tracks`
- 核心配置 `voiceProfile` `speed` `emotion`
- 可回写 是 回写 `AudioAsset[]`
- 验收标准 输出可用于 Animatic 的对齐音轨

### 3.15 `AnimaticNode` 预演节点

- 分组 输出节点
- 作用 把静帧 时长 字幕和音轨合成为预演视频
- 输入端口 `images` `audio_tracks` `shots`
- 输出端口 `animatic_video`
- 核心配置 `fps` `transitionPreset` `subtitleMode`
- 可回写 是 回写 `Animatic`
- 验收标准 可播放 可审片 可定位回上游 Shot

---

## 4. 节点端口与数据 Schema 建议

- `raw_document` 原始文本或文档对象
- `normalized_text` 清洗后的标准文本
- `chapters` 章节数组
- `characters` 角色数组
- `locations` 场景地点数组
- `story_bible` 故事圣经对象
- `beats` Beat 数组
- `scenes` Scene 数组
- `shots` Shot 数组
- `visual_prompts` Prompt 数组
- `images` 图像工件数组
- `audio_tracks` 音频工件数组
- `review_report` 审查结果数组
- `animatic_video` 预演视频工件 

---

## 5. 验收与测试建议

### 5.1 节点级验收

- 每个节点都必须有输入满足与输入缺失两类测试
- 每个节点都必须有成功态和失败态展示
- 每个节点都必须有结果摘要卡
- 可回写节点必须有回写成功和回写失败测试

### 5.2 工作流级验收

- 黄金链路 导入 分析 Beat Scene Shot Prompt 图像 TTS Animatic 可从头跑通
- 单节点失败后 下游节点应进入 blocked
- 用户可在不丢失结果的情况下重跑失败节点

### 5.3 未来扩展要求

- 所有新节点都必须复用统一 BaseNodeSpec
- 所有新节点都必须声明 editionRequired
- 所有新节点都必须定义回写规则
- 所有新节点都必须定义最小结果摘要样式

---

## 6. 本文档结论

影视创作画布的节点系统必须围绕 结构化中间层 可执行编排 结果可视化和回写可控 四个核心目标设计。
在 Phase 1 只应优先实现黄金链路节点 不建议同时引入过多高级节点。 
