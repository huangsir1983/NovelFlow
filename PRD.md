# 虚幻造物 (Unreal Make) — 产品需求文档

> 版本: 6.2 | 日期: 2026-03-06
> 知识库目录: `知识库/`
> 界面设计规范: `NovelFlow-main/界面设计规范/`

---

## 一、产品概述

### 1.1 产品定位

AI-Native 全节点可视化影视创作引擎。从小说/剧本文本到完整视频的端到端 AI 辅助创作系统。
核心架构：**三段式工作台 + Tapnow式可执行无限画布 + Agent Pipeline + Cinema Lab 电影实验室**。
Web + 桌面(Win/Mac)双端，多版本产品体系，核心模块 Agent 化，支持团队协同与工作流社区分享。
内置专业级导演分镜知识体系 + 编剧知识体系 + 电影级物理控制，面向奥斯卡级电影品质与国内顶级 AI 微短剧。

### 1.2 目标用户

| 版本 | 用户画像 | 核心需求 |
|------|---------|---------|
| 普通版 Normal | 个人创作者/小白 | 零门槛完成小说→分镜全流程 |
| 画布版 Canvas | 团队/影视公司 | 节点画布 + 多人协作 + 专业编剧工具 |
| 隐藏版 Hidden | 合作方(邀请制) | 全模块 + Cinema Lab + 可定制知识库 |
| 自用版 Ultimate | 内部使用 | 全功能 + 调试 + 数据闭环 + 节点嵌套 |

---

## 二、核心流程

### 2.1 双入口节点化架构

```
[入口层]
  小说导入(TXT/DOCX/EPUB/PDF/MD) ──┐
  剧本导入(Fountain/FDX/TXT/DOCX)──┼──► [分析层]
  从零创建[Ultimate] ───────────────┘      小说分析师 / 剧本适配引擎
                                                │
                                           [知识层]
                                           项目知识库(角色/场景/世界观)
                                           ◄── 一致性守护(全局枢纽)
                                                │
                                           [资产层]
                                      资产库(跨项目可复用素材: 角色/道具/场景/光线/动作)
                                      三级: 公用(官方免费+社区付费) / 自用 / 项目内
                                                │
                                           [创作层]
                                      Beat Sheet + 张力引擎
                                                │
                                      编剧工作台(原点10+4专家)
                                      微短剧编剧[Ultimate]
                                                │
                                           [导演层]
                                      导演分镜(7步+5序列)
                                      ├── 声音叙事设计
                                      ├── 场面调度
                                      ├── 文化视觉适配
                                      └── Cinema Lab 电影实验室
                                                │
                                           [视觉层]
                                      视觉Prompt工程(9模块+20检)
                                      视觉母题追踪终检
                                                │
                                           [生成层]
                                      AI图像/视频生成 + TTS + AI音乐
                                                │
                                           [输出层]
                                      剪映工程包(Draft) + 宣发物料
                                      导出(PDF/格式包) + 数据反馈[U]
```

用户在**无限画布**上以节点形式看到整个流程，节点间连线代表数据流。每个节点实时显示运行状态和输出预览。

### 2.2 剧本导入适配引擎 (入口B)

用户直接导入已有剧本时，经过四步适配对接下游分镜流程：

| 步骤 | 内容 | Prompt ID | 模型 |
|------|------|-----------|------|
| Step 1 | 格式识别与标准化: Fountain/FDX/自由格式→内部JSON | PS01 | Haiku, t=0.2 |
| Step 2 | 结构分析: Act识别→逆向Beat Sheet→情感曲线→节奏密度 | PS02 | Sonnet, t=0.4 |
| Step 3 | 知识库逆向构建: 角色档案→场景档案→关系推断→世界观→Story Bible | PS03 | Sonnet, t=0.4 |
| Step 4 | 质量评估与适配优化: 分镜可执行性评估→补充描述→优化建议 | PS04/PS05 | Sonnet, t=0.3/0.6 |

---

## 三、功能模块

### 3.1 核心模块 (所有版本)

- **小说解析管线**: 上传→分章→角色提取→场景提取→知识库初始化
- **资产库管理**: 跨项目可复用素材系统(角色/道具/场景/光线/动作/风格), 三级管理(公用资产-官方免费+社区付费 / 自用资产-跨项目 / 项目内资产), 支持预览/编辑/重生成, 项目引用时可覆盖+锁定 → 下游视觉一致性锚点
- **Beat Sheet 编辑器**: AI 生成 + 手动调整 + 情感曲线可视化
- **剧本编辑器**: TipTap 富文本 + AI 辅助(改写/扩写/缩写/对话优化)
- **分镜脚本生成器**: 场景→镜头拆解 + 分镜卡片 + 时间轴视图
- **视觉 Prompt 引擎**: 分镜→AI 绘图 Prompt (多平台适配) + 角色资产锚定
- **剪映工程包导出**: AI生成素材→剪映Draft文件(视频+音频+字幕+时间线+导演标记) → 用户在剪映中精剪
- **导出系统**: PDF / JSON / Fountain / FDX / CSV / DOCX

### 3.2 编剧系统 — "原点"编剧体系 (Canvas+)

10 位子专家协作模式:

```
基础子专家 (Canvas+):
  @StructureGenius    — 结构设计
  @SceneCrafter       — 场景构建
  @WorldBuilder       — 世界观
  @ActionChoreographer — 动作编排
  @DialogueDoctor     — 对白设计
  @EmotionResonance   — 情感共鸣
  @SubtextExpert      — 潜台词
  @RhythmController   — 节奏控制
  @VisualHammer       — 视觉锤
  @CharPsychologist   — 角色心理

增强子专家 (Hidden+):
  @ThemeArchaeologist — 主题三层挖掘 + 多义性 + 隐喻系统
  @TimelineArchitect  — 非线性叙事 + 多时间线管理 + 信息不对称设计
  @DialogueDoctor v2  — 对白节奏韵律 + 意象运用 + 大师风格参考
  @CharPsychologist v2 — 矛盾性设计 + 灰色地带 + 无意识驱动
```

附加: Intent Anchor 管理器 + Sandbox 模式 + 创作风格记忆

### 3.3 微短剧编剧系统 (Ultimate)

11 节点流水线 + 爽点引擎(3层) + 付费卡点优化 + 性别向调优 + 小说改编专用模块

### 3.4 导演分镜系统 (Hidden+)

```
核心: 7步执行流 + 8列输出 + 14种转场 + 16点质检
高级: 6大模块(角色深度/镜头语言/动作拆解/对白精修/高级转场/终极戒律)
序列设计器(5种): 动作/对白/情感/蒙太奇/悬疑 (按场景类型自动选择)
```

### 3.5 Cinema Lab 电影实验室 (Hidden+)

导演 Agent + 视觉 Agent 子系统，在画布中作为导演节点的展开面板呈现。输出 `cinema_lab` JSON 对象。

#### 3.5.1 六大子模块

```
1. Lens Combo (真实镜头库)
   - 镜头品牌: ARRI Signature / Cooke S7i / Zeiss Supreme / Panavision
   - 参数: 焦距(18-300mm) / 光圈(f/1.4-f/22)
   - 镜头特性: 色散/暗角/畸变/散景形状
   - 与文化预设联动: 武侠→Cooke(飘逸) / 好莱坞→ARRI(锐利) / 欧洲→Zeiss(自然)

2. Multi-Angle 3D Manipulator (3D机位控制)
   - 可拖拽3D控件→实时改变摄影机角度
   - 参数: 方位角/仰角/距离/焦点
   - 与导演7步联动: Step 3镜头选择→自动设置初始机位
   - 预设: 正面/侧面/俯视/低角度/过肩/POV

3. Studio Lighting (影棚灯光系统)
   - 三点布光: Key/Fill/Rim Light
   - 每盏灯: 位置(拖拽)/色温(2700K-10000K)/亮度(0-100%)
   - 光质: 硬光(Fresnel)/柔光(Softbox)/散射(Diffusion)
   - 文化预设联动: 古装→暖调烛光 / 韩式→柔光Softbox / 好莱坞→标准三点

4. Motion Library & Pose Control (动作与姿态)
   - 动作参考库 + 自定义上传
   - 姿态骨架编辑器
   - 与场面调度联动: 走位序列→动作关键帧
   - 与爽点联动[U]: 打脸→表情特写 / 逆袭→英雄站姿

5. Point-to-Edit & Object Replacement (精确编辑)
   - 生成图/视频中点选物体→替换/移除/修改
   - 保持光影/运动连续性
   - 与视觉母题联动: 母题道具标记"不可替换"

6. AI Storyboarding (智能分镜可视化)
   - 输入场景描述→自动生成参考分镜图
   - 风格: 手绘素描/3D预览/真实感
   - 与导演分镜网格联动
```

#### 3.5.2 Cinema Lab 数据模型

```typescript
interface CinemaLabConfig {
  lens_combo: {
    brand: string;           // "ARRI Signature" | "Cooke S7i" | ...
    focal_length: number;    // mm
    aperture: number;        // f-stop
    characteristics: {
      chromatic_aberration: number; // 0-1
      vignetting: number;
      distortion: number;          // -1 to 1
      bokeh_shape: string;         // "circular" | "oval" | "cat-eye"
    };
  };
  camera_3d: {
    azimuth: number;         // 0-360 degrees
    elevation: number;       // -90 to 90
    distance: number;
    focal_point: [number, number, number];
    motion_path?: MotionKeyframe[];
  };
  lighting_setup: {
    key_light: LightConfig;
    fill_light: LightConfig;
    rim_light: LightConfig;
    ambient: { color_temp: number; intensity: number };
    practicals?: LightConfig[];
  };
  motion_pose: {
    reference_id?: string;
    custom_skeleton?: JointAngles;
    motion_speed: number;    // 0.1x ~ 4x
  };
  edit_instructions?: EditInstruction[];
  storyboard_style: "sketch" | "3d_preview" | "photorealistic";
}

interface LightConfig {
  position: [number, number, number];
  color_temp: number;        // Kelvin
  intensity: number;         // 0-100
  quality: "hard" | "soft" | "diffused";
  modifier?: string;         // "fresnel" | "softbox" | "beauty_dish"
}
```

#### 3.5.3 Cinema Lab Prompt 模板

| ID | 名称 | 模型 | 温度 | 说明 |
|----|------|------|------|------|
| CL01 | 镜头特性转Prompt | Haiku | 0.2 | lens_combo→色散/散景/质感文本 |
| CL02 | 3D机位转Prompt | Haiku | 0.2 | camera_3d→"low angle, 45° side" |
| CL03 | 灯光转Prompt | Haiku | 0.2 | lighting→"warm key, cool rim" |
| CL04 | 动作姿态转Prompt | Sonnet | 0.3 | motion_pose→自然语言动作描述 |
| CL05 | Cinema Lab综合 | Sonnet | 0.4 | 合并CL01-04+场景上下文→完整Prompt |

#### 3.5.4 Cinema Lab 与其他模块联动

| 联动模块 | 联动方式 | 方向 |
|----------|---------|------|
| 导演7步流程 | Step 3镜头选择→自动设置Lens+Camera | 导演→Lab |
| 5种序列设计器 | 序列模板→预设机位运动轨迹 | 导演→Lab |
| 声音叙事 | 灯光氛围↔声音氛围同步 | 双向 |
| 场面调度 | 走位序列→Motion关键帧 | 调度→Lab |
| 文化视觉适配 | 文化预设→推荐Lens+Lighting组合 | 文化→Lab |
| 爽点视觉联动[U] | 爽点类型→Cinema Lab参数突变 | 爽点→Lab |
| 视觉母题 | 色彩弧→Lighting色温约束 | 母题→Lab |
| 视觉Prompt工程 | Lab参数→嵌入Prompt末段 | Lab→Prompt |

### 3.6 声音叙事系统 (Hidden+)

导演 Agent 子模块，为每个镜头生成 `sound_narrative` 对象。

```
1. 三层环境声设计:
   Layer 1: 底噪层 (空间声特征)
   Layer 2: 环境活动层 (背景人声/动物/机械/自然)
   Layer 3: 焦点音效层 (与叙事直接相关)
2. 音乐情感映射引擎: 12条映射 + 动机追踪 + 入出点标注
3. 静默运用规则: 高冲击/过渡/叙事静默
4. 声音转场设计: J-cut/L-cut/声音桥/音量渐变
5. 音画关系标注: 同步/对位/分离
```

### 3.7 视觉母题追踪系统 (Hidden+)

一致性守护 Agent 子模块，分镜完成后自动扫描全片生成《视觉叙事报告》。

```
1. 视觉符号提取与登记 (3-5个核心视觉符号)
2. 色彩叙事弧规划 (全片色温曲线/角色专属色彩/情感色彩映射)
3. 构图回响检测 (开头/结尾呼应/重要场景变奏)
4. 母题密度控制 (开头暗示→中段强化→高潮爆发→尾声回响)
5. 跨镜头视觉连贯性 (色彩/道具/光影连续性)
```

### 3.8 场面调度系统 (Hidden+)

导演 Agent 子模块，适用于重要对话、群戏、长镜头、复杂动作场景。输出 `mise_en_scene` 对象。

```
1. 演员位置标注: 俯视图 + 初始/终止位置 + 关键时间点快照
2. 走位路线设计: 移动轨迹 + 动机 + 与台词时序关系
3. 空间叙事层次: 前景/中景/背景 + 景深叙事含义
4. 群戏编排: 注意力引导 + 空间主次 + 进出场时序
5. 长镜头设计: 走位+机位时序图 + 焦点转移计划
```

### 3.9 情感张力量化引擎 (Canvas+)

编剧 Agent + 导演 Agent 共享。输出全片/分幕/分场景张力图表 + 节奏优化建议。

```
1. 多维张力模型:
   叙事张力(信息落差) / 情感张力(困境x共情)
   时间张力(截止期限x紧迫度) / 道德张力(伦理困境两难)
   综合张力 = f(叙事,情感,时间,道德) → 0-100分
2. 张力曲线规划: 经典三幕/W型/阶梯型/下沉-爆发型
3. 节奏密度分析: 场景时长 vs 对话密度 vs 动作密度 + "呼吸点"检测
4. 观众疲劳预测: 认知负荷衰减 + "刺激过载/不足"标注
```

### 3.10 跨文化视觉语言适配 (Hidden+)

导演 Agent 子模块，基于 genre + 目标受众自动推荐视觉语言预设。

```
中国武侠: 写意远景/飘逸运镜/静→动突转/诗意空镜
中国古装: 对称构图/色彩象征/仪式感镜头/庭院空间
韩式情感: 柔光特写/慢速推进/OST标注/雨景运用
好莱坞商业: 三分法/快节奏剪辑/大特效全景/英雄低角度
欧洲艺术: 长镜头/自然光/固定机位/留白
日式动画: 极端透视/速度线/表情夸张/定格
支持混合预设 + 文化冲突检测
```

### 3.11 爽点视觉联动 (Ultimate)

微短剧编剧 Agent 标注爽点→导演 Agent 选择视觉增强→视觉 Agent 嵌入参数。

```
反转 → 镜头突变(固定→手持) + 音乐突变
打脸 → 表情特写序列(ECU) + 正反打加速 + 定格
逆袭 → 低角度英雄镜头 + 背光剪影 + 升格慢动作
甜蜜 → 柔光滤镜 + 浅景深 + 暖色调 + 慢推
释放 → 远景→近景快切 + 动态构图 + 强音乐
```

### 3.12 数据反馈闭环 (Ultimate)

```
1. 数据采集: 对接抖音/快手/微信视频号API
   收集完播率/互动率/分享率/付费率/弹幕热词
2. 内容-数据关联分析: 指标映射到内容结构特征→归纳高效/失效模式
3. 知识库沉淀: project-level + platform-level 两级知识库
4. 反哺创作: 新项目检索历史数据模式→创作参考 + 预测性评分
```

### 3.13 IP 延展规划 (Canvas+)

项目完成后自动生成 IP 评估报告：系列化潜力评估 / 续集钩子设计 / 衍生内容方向 / 粉丝运营素材 / IP 核心资产清单

---

## 四、节点画布系统

### 4.1 画布架构

```
+----------------------------------------------------------------------+
| [Glass TopBar 48px]                                                   |
| UM Logo | 项目名 | 工作流:v3 | ---- | [协作] [分享] [▶ Run全链路]     |
+----------------------------------------------------------------------+
|                                                                       |
|               无限画布 (Infinite Canvas)                               |
|          React Flow / @xyflow/react v12                               |
|                                                                       |
+------------------+-----------------------------------+-----------------+
| [左侧浮动]       |        主画布区域                   | [右侧浮动]      |
| 节点库           |        (>=70% 屏幕面积)            | 节点属性面板     |
| 可折叠/拖拽添加  |                                   | Cinema Lab控件  |
+------------------+-----------------------------------+-----------------+
| [底部浮动] minimap | 适应屏幕 | [-][100%][+] | 锁定 | 快捷键          |
+----------------------------------------------------------------------+
```

### 4.2 节点类型系统 (8大类)

#### 输入节点 (蓝色 #3b82f6)
| 节点 | 功能 | 版本 |
|------|------|------|
| 小说导入 | TXT/DOCX/EPUB/PDF/MD | All |
| 剧本导入 | Fountain/FDX/TXT/DOCX/PDF | Canvas+ |
| 从零创建 | 空白项目+世界观模板 | Ultimate |

#### 分析节点 (紫色 #8b5cf6)
| 节点 | 功能 | 版本 |
|------|------|------|
| 小说分析师 | 分章+角色+场景+知识库初始化 | Canvas+ Agent / Normal后台 |
| 剧本适配引擎 | PS01-PS05四步适配 | Canvas+ |
| 知识库 | 角色/场景/世界观/风格编辑+审核 | All |

#### 资产节点 (橙色 #f97316)
| 节点 | 功能 | 版本 |
|------|------|------|
| 资产库 | 跨项目可复用素材(角色/道具/场景/光线/动作/风格), 三级scope(公用/自用/项目), 支持预览/编辑/重生成 | All (分层) |
| 资产引用 | 将资产库素材引入当前项目, 可覆盖属性+锁定, 锁定后成为视觉Prompt强制锚点 | All |

#### 创作节点 (绿色 #22c55e)
| 节点 | 功能 | 版本 |
|------|------|------|
| Beat Sheet | 情感曲线+结构规划 | All |
| 编剧工作台 | 原点10+4专家 | Canvas+(10) / Hidden+(+4) |
| 微短剧编剧 | 11节点+爽点引擎 | Ultimate |
| IP延展规划 | 系列化评估+衍生建议 | Canvas+ |

#### 质检节点 (青色 #06b6d4)
| 节点 | 功能 | 版本 |
|------|------|------|
| 一致性守护 | 全局枢纽,自动连接所有内容节点 | Canvas+ |
| 张力引擎 | 多维张力模型+曲线可视化 | Canvas+(标准) / Hidden+(完整) |
| 视觉母题追踪 | 色彩弧+构图回响+母题密度 | Hidden+ |
| 质量审核 | 声音/调度/张力/母题终检 | Hidden+ |

#### 导演节点 (红色 #ef4444)
| 节点 | 功能 | 版本 |
|------|------|------|
| 导演分镜 | 7步+5序列+分镜网格 | Hidden+(完整) / Canvas+(基础) |
| 声音叙事 | 三层环境声+音乐+静默+转场 | Hidden+ |
| 场面调度 | 位置图+走位+群戏+长镜头 | Hidden+ |
| 文化视觉适配 | 6种预设+混合+冲突检测 | Hidden+ |
| Cinema Lab | Lens+3D+Lighting+Motion+Edit | Hidden+ |
| Animatic预览 | 分镜→动态预览视频(低成本节奏验证) | Canvas+ |

#### 视觉节点 (黄色 #eab308)
| 节点 | 功能 | 版本 |
|------|------|------|
| 视觉Prompt工程 | 9模块+20检+多平台 | Hidden+(完整)/Canvas+(基础) |
| 爽点视觉联动 | 爽点类型→视觉增强 | Ultimate |

#### 生成节点 (品红 #d946ef)
| 节点 | 功能 | 版本 |
|------|------|------|
| AI图像生成 | Kling/即梦/MJ/SD-Flux | Canvas+ |
| AI视频生成 | Kling/即梦视频API | Canvas+ |
| TTS语音 | 语音合成+配音 | Canvas+ |
| AI音乐 | Suno/Udio + 声音叙事联动 | Canvas+ |

#### 输出节点 (灰色 #6b7280)
| 节点 | 功能 | 版本 |
|------|------|------|
| 剪映工程包 | Draft导出(视频+音频+字幕+时间线+导演标记) | All (分层) |
| 宣发物料 | 封面/海报/预告片草稿 | All (分层) |
| 导出 | PDF/JSON/Fountain/FDX/CSV/DOCX | All |
| 数据反馈 | 对接平台API+分析+沉淀 | Ultimate |

### 4.3 节点视觉设计

```css
.nf-node {
  background: #12122a;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  min-width: 280px; max-width: 360px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.nf-node-header { padding: 10px 14px; font-size: 13px; font-weight: 600; }
/* 每类节点头部背景使用对应色系 rgba(color, 0.15) */

.nf-node.selected { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,0.3); }
.nf-node.running  { border-color: #3b82f6; animation: nodePulse 2s infinite; }
.nf-node.error    { border-color: #ef4444; }
.nf-node.success  { border-color: #22c55e; }
.nf-node.locked   { opacity: 0.5; filter: grayscale(0.5); }

.nf-edge          { stroke: rgba(255,255,255,0.15); stroke-width: 2px; }
.nf-edge.active   { stroke: #6366f1; stroke-dasharray: 8; animation: flowDash 1s linear infinite; }
.nf-edge.conflict { stroke: #f59e0b; stroke-width: 3px; }

.nf-handle { width: 12px; height: 12px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.3); }
.nf-handle:hover { border-color: #6366f1; transform: scale(1.3); }
```

### 4.4 画布交互

```
鼠标拖拽空白     → 平移画布
滚轮            → 缩放 (10%-200%)
双击节点        → 展开全屏编辑器 (Portal)
点击节点        → 选中 + 右侧属性面板更新
拖拽端口→端口   → 创建连接 (类型校验)
框选            → 多选
右键节点        → 上下文菜单 (运行/复制/删除/替换)
Tab             → 快速节点选择器 (模糊搜索)
Cmd+Enter       → 运行选中节点
Cmd+Shift+Enter → 运行全链路
Cmd+Z/Y         → 撤销/重做
Cmd+C/V         → 复制粘贴
Cmd+\           → 适应屏幕
Cmd+F           → 搜索节点

运行机制:
  单节点▶ → 从上游获取最新数据→执行
  全链路▶ → 拓扑排序→同层并行→依次执行→流动动画
  一致性守护 → 自动连接所有内容节点, 冲突时连线变橙色+警告徽章
```

### 4.5 节点库面板

```
▾ 输入: 小说导入 / 剧本导入 / 从零创建[U]
▾ 分析: 小说分析师 / 剧本适配引擎 / 知识库
▾ 资产: 资产库 / 资产引用
▾ 创作: Beat Sheet / 编剧工作台 / 微短剧编剧[U] / IP延展
▾ 质检: 一致性守护 / 张力引擎 / 视觉母题[H+] / 质量审核[H+]
▾ 导演: 导演分镜 / 声音叙事[H+] / 场面调度[H+] / 文化适配[H+] / Cinema Lab[H+] / Animatic预览
▾ 视觉: 视觉Prompt / 爽点联动[U]
▾ 生成: AI图像 / AI视频 / TTS / AI音乐
▾ 输出: 剪映工程包 / 宣发物料 / 导出 / 数据反馈[U]

[H+]=Hidden以上  [U]=Ultimate专属  锁定节点显示灰色+🔒
```

### 4.6 工作流模板

| 模板名 | 节点数 | 版本要求 | 说明 |
|--------|--------|---------|------|
| 小说转视频标准版 | 10 | Normal+ | 小说→分析→知识库+资产→Beat→剧本→分镜→Prompt→生成→剪映包 |
| 剧本直通快速版 | 5 | Canvas+ | 剧本→适配→分镜→Prompt→剪映包 |
| 电影级制作 | 20 | Hidden+ | 双入口→资产+美术总设计→原点10专家→导演7步+Cinema Lab+声音→视觉9模块→母题终检→剪映包+宣发 |
| 微短剧全链路 | 18 | Ultimate | 小说→资产→微短剧11节点→爽点→导演+Cinema Lab→视觉→剪映包+宣发+数据反馈 |
| 从空白开始 | 0 | Canvas+ | 自由拖入节点组合 |
| 从社区克隆 | - | Canvas+ | 浏览 Marketplace |

### 4.7 版本画布能力

| 能力 | Normal | Canvas | Hidden | Ultimate |
|------|--------|--------|--------|----------|
| 画布模式 | 向导式锁定 | 自由画布 | 自由+Cinema Lab | 自由+嵌套+调试 |
| 节点连线 | 不可修改 | 自由 | 自由 | 自由+子流程 |
| 可用节点 | 7种 | 18种 | 全部 | 全部+实验 |
| 全链路Run | 自动 | 手动/自动 | 手动/自动 | +后台批量 |
| 节点内调试 | 无 | 无 | 无 | Prompt/Token/耗时/模型 |

---

## 五、Flow Marketplace 工作流社区

### 5.1 机制

```
创作者完成项目 → 一键"发布到 Marketplace"
  → 自动脱敏(移除私有内容,保留结构+配置)
  → 生成公开链接: /marketplace/view/{slug}

浏览者 → 搜索/分类/精选 → 查看拓扑(只读)+效果预览
  → "克隆" → 复制到自己画布 → 替换输入 → 运行

功能:
  - Fork后修改→发布为新变体 (归因链)
  - 评分 + 评论 + 使用统计
  - 分类标签: 古装/现代/悬疑/爱情/科幻/微短剧/广告
  - 精选推荐 (编辑+算法)
  - 付费工作流 (Phase 7+)
```

### 5.2 URL 结构

```
/marketplace/view/{slug}  → 工作流只读预览+克隆
```

---

## 六、版本矩阵

```
+----------+----------+----------+----------+-------------------------+
|          | Normal   | Canvas   | Hidden   | Ultimate               |
+----------+----------+----------+----------+-------------------------+
| 画布     | 向导锁定  | 自由画布  | +Cinema  | +嵌套+调试              |
| 节点数   | 7        | 20       | 全部      | 全部+实验               |
| 入口     | 小说     | +剧本    | +剧本    | +从零创建               |
| 资产库   | 项目内   | +自用资产 | +公用浏览 | +社区分享+收费           |
|          | (基础)   | +跨项目   | +编辑重生 | +全类型+自定义           |
| Agent    | 无       | 3核心    | 6个      | 9个+编排器              |
| 编剧     | 基础     | 10专家   | +4增强   | +微短剧双系统           |
| 分镜     | Core    | Core+Adv | +Cinema  | +Cinema                |
| Animatic | 无       | 基础     | 完整     | 完整                    |
| 声音叙事 | 基础标注 | 基础标注  | 完整     | 完整                    |
| 场面调度 | 无       | 无       | 完整     | 完整                    |
| 张力引擎 | 简化     | 标准     | 完整     | +数据反馈               |
| 视觉母题 | 无       | 无       | 完整     | 完整                    |
| 文化适配 | 无       | 无       | 6预设    | +自定义                 |
| 剪映工程包| 基础    | 完整Draft | +调色建议 | +调试元数据             |
| 宣发物料 | 封面1张  | 封面+海报 | +预告草稿 | +批量A/B               |
| AI音乐   | 无      | 1条      | 多条     | 多条+分层               |
| 数据反馈 | 无       | 无       | 基础报告  | 完整闭环+沉淀           |
| Marketplace| 浏览3次 | 克隆+发布| 无限     | +管理                   |
| 协作     | 单人     | 多人画布 | +API     | 不限                    |
| 候选数   | 1       | 3       | 5        | 不限                    |
| 模型选择 | 无      | 无       | 可选     | +调试                   |
| 默认模型 | Haiku   | Sonnet   | Sonnet   | Opus                    |
| 导出     | PDF/JSON| 全格式   | 全格式   | 全格式                  |
| 桌面端   | 无      | 有       | 有       | 有                      |
| 自定义Prompt| 无   | 微调     | 完全     | 完全                    |
| 自定义知识库| 无   | 查看     | 编辑     | 完全+热加载             |
+----------+----------+----------+----------+-------------------------+
```

### 版本控制实现

```typescript
enum Edition {
  NORMAL = 'normal',
  CANVAS = 'canvas',
  HIDDEN = 'hidden',
  ULTIMATE = 'ultimate',
}
```

完整 `FEATURE_FLAGS` 定义参见代码 `packages/shared/src/lib/featureFlags.ts`。

---

## 七、智能 Agent 体系 (9 Agents)

### 7.1 架构

```
+------------------------------------------------------------+
|              Agent Coordinator (Ultimate)                    |
+-----------------------------+------------------------------+
                              |
  +--------+--------+---------+--------+--------+--------+
  v        v        v         v        v        v        v
分析师   编剧     微短剧编剧  导演    视觉     审核官   数据优化
Agent   Agent    Agent[U]   Agent   Agent    Agent    Agent[U]
        10+4专家  11节点     7步+5器  9模块+20检
        +增强    +爽点引擎   +声音    +平台适配
                            +调度    +边缘案例
                            +Cinema Lab
                            +文化适配
                              |
                +-------------v--------------+
                |   一致性守护 Agent          |
                |   + 视觉母题追踪           |
                |   + 张力曲线监控           |
                +----------------------------+
```

### 7.2 Agent 定义

| # | Agent | 版本 | 触发 | 职责 |
|---|-------|------|------|------|
| 1 | 小说分析师 | Canvas+ | 文件上传 | 分章→角色→场景→知识库; 剧本逆向构建 |
| 2 | 一致性守护 | Canvas+ | 内容变更/定时 | 即时校验+视觉母题追踪+张力监控; 全局枢纽节点 |
| 3 | 编剧(原点) | Canvas+ | 知识库确认 | 10子专家+4增强(Hidden+); Beat→场景生成 |
| 4 | 微短剧编剧 | Ultimate | 知识库确认 | 11节点+爽点引擎+付费卡点 |
| 5 | 导演 | Hidden+ | 剧本定稿 | 7步+5序列+声音叙事+场面调度+文化适配+Cinema Lab参数生成 |
| 6 | 视觉Prompt | Hidden+ | 分镜完成 | 9模块+20检+多平台(Kling/即梦/MJ/SD-Flux)+边缘案例 |
| 7 | 质量审核 | Hidden+ | 分镜/Prompt完成 | 声音完整度+调度合理性+张力达标+母题覆盖率 |
| 8 | 数据优化 | Ultimate | 每日 | 完播率预测+付费转化+A/B版本+知识库沉淀 |
| 9 | 协调者 | Ultimate | 全局 | 全自动管线编排, 10步Stage推进 |

### 7.3 Agent 节点化映射

```python
NODE_TO_AGENT = {
    "novel_analyst": "analyst",
    "script_adapter": "analyst",
    "knowledge_base": None,           # 纯数据节点
    "beat_sheet": "screenwriter",
    "screenwriter": "screenwriter",
    "micro_drama": "micro_drama_writer",
    "director": "director",
    "sound_narrative": "director",
    "mise_en_scene": "director",
    "cultural_visual": "director",
    "cinema_lab": "director",
    "visual_prompt": "visual",
    "thrill_visual": "visual",
    "consistency": "consistency",
    "tension_engine": "consistency",
    "visual_motif": "consistency",
    "quality_reviewer": "reviewer",
    "image_gen": None,                # 直接调用生成API
    "video_gen": None,
    "tts": None,
    "ps_agent": None,
    "export": None,
    "data_feedback": "data_optimizer",
}
```

### 7.4 Agent 运行时架构

Agent 不是常驻进程，而是**事件驱动的 Celery Worker**。通过钩子触发，按需唤醒。

#### 生命周期状态机

```
DORMANT(版本不支持) → IDLE → RUNNING → IDLE
                              ↓
                          WAITING(等待用户/其他Agent/重试)
状态持久化: Redis Hash  agent:{agent_id}:status
前端同步: WebSocket推送→节点状态实时更新
```

#### 钩子触发体系

```
1. 管线钩子 (Pipeline Hooks):
   文件上传完成    → 分析师Agent
   知识库确认      → 编剧Agent
   剧本定稿       → 导演Agent + 声音叙事(并行)
   分镜完成       → 视觉Agent + 一致性Agent(母题终检)
   Prompt完成     → 生成管线

2. 内容钩子 (Content Hooks):
   剧本变更(防抖2s) → 一致性Agent(增量校验)
   角色档案修改     → 一致性Agent(关联检查)
   分镜参数修改     → 视觉Agent(重新生成Prompt)
   张力值手动调整   → 一致性Agent(曲线重算)

3. 定时钩子 (Schedule Hooks):
   每30分钟(活跃项目) → 一致性Agent(全局扫描)
   每小时            → 张力模块(偏离检测)
   每天              → 数据优化Agent(拉取数据)

4. Agent间钩子 (Inter-Agent):
   编剧(场景完成) → 一致性(校验)
   一致性(冲突)   → 编剧(修正)
   导演(分镜完成) → 视觉(Prompt)
   审核(不达标)   → 编剧/导演(修正, 最多3轮)
   微短剧(爽点)   → 导演(爽点视觉增强)
   协调者         → 任意Agent(调度指令)
```

#### 事件总线 (AgentBus)

```python
class Event:
    id: UUID
    type: str                    # "pipeline.script_finalized" / "content.changed" / ...
    project_id: UUID
    source: str                  # "api" / "user" / "agent:director" / "scheduler"
    payload: dict
    timestamp: datetime
    trace_id: UUID               # 链路追踪

class AgentBus:
    """基于Redis Pub/Sub + Stream"""
    CHANNELS = {
        "pipeline.*":     "管线阶段事件",
        "content.*":      "内容变更事件",
        "agent.{name}.*": "Agent私有频道",
        "system.*":       "系统事件",
    }

AGENT_SUBSCRIPTIONS = {
    "analyst":     ["pipeline.file_uploaded", "pipeline.script_uploaded"],
    "consistency": ["pipeline.*", "content.*", "agent.consistency.*"],
    "screenwriter":["pipeline.knowledge_confirmed", "agent.screenwriter.*"],
    "director":    ["pipeline.script_finalized", "agent.director.*"],
    "visual":      ["pipeline.storyboard_complete", "agent.visual.*"],
    "reviewer":    ["pipeline.storyboard_complete", "pipeline.prompt_complete"],
    "micro_drama": ["pipeline.knowledge_confirmed", "agent.micro_drama.*"],
    "data_optimizer": ["pipeline.published", "scheduler.daily"],
    "coordinator": ["pipeline.*", "agent.*"],
}
```

#### 任务队列

```python
QUEUES = {"critical": 0, "pipeline": 1, "background": 2}

RETRY_POLICY = {
    "max_retries": 3,
    "retry_backoff": True,           # 10s → 30s → 90s
    "retry_backoff_max": 300,
    "retry_on": [APITimeoutError, RateLimitError],
    "no_retry_on": [ValidationError, EditionNotAllowed],
}

TIMEOUTS = {
    "analyst": 300, "screenwriter": 180, "director": 120,
    "visual": 60, "consistency": 60,
}

FALLBACK = {
    "opus_unavailable": "降级到sonnet",
    "sonnet_unavailable": "降级到haiku + 标记需人工审核",
    "all_unavailable": "任务挂起 + 通知用户",
}

# Worker路由: 每种Agent独立queue
celery_app.conf.task_routes = {
    "agents.analyst.*":      {"queue": "agent-analyst"},
    "agents.screenwriter.*": {"queue": "agent-screenwriter"},
    "agents.director.*":     {"queue": "agent-director"},
    "agents.visual.*":       {"queue": "agent-visual"},
    "agents.consistency.*":  {"queue": "agent-consistency"},
    "agents.coordinator.*":  {"queue": "agent-coordinator"},
}
```

#### LLM 调用层

```python
class AIEngine:
    """统一LLM调用入口。心跳由Celery Worker维持,不受LLM调用阻塞。"""

    async def call(self, prompt, model="sonnet", task_id=None, timeout=120, stream=True):
        model_config = self._resolve_model(model)
        start = time.monotonic()
        response = await self._stream_call(prompt, model_config, timeout)
        elapsed = time.monotonic() - start
        await self._log_call(task_id, model, elapsed, response.usage)
        return response

    def _resolve_model(self, requested):
        return {"opus": "claude-opus-4-6", "sonnet": "claude-sonnet-4-6", "haiku": "claude-haiku-4-5-20251001"}[requested]

class ModelFallbackManager:
    FALLBACK_CHAIN = ["opus", "sonnet", "haiku"]
    # 降级时: 每次调用传入完整上下文, haiku使用简化Prompt
```

#### 健康保活

```
心跳: Worker每30秒上报Redis, 不经过LLM, >90秒无心跳→UNHEALTHY→重启
超时: soft_time_limit(异常可收尾) + hard_time_limit(强制kill, soft+30s)
断路器: 连续3次同类型失败→打开→30秒后半开→成功→关闭
监控指标: 状态/任务/队列深度/成功率/延迟/断路器/降级次数
```

#### 协调者管线编排 (Ultimate)

```python
PIPELINE_STAGES = [
    Stage("import",       agents=["analyst"]),
    Stage("knowledge",    agents=["analyst"],       wait_user=True),
    Stage("beat_sheet",   agents=["screenwriter"]),
    Stage("script",       agents=["screenwriter", "micro_drama"]),
    Stage("review",       agents=["consistency", "reviewer"],  max_rounds=3),
    Stage("data_optimize",agents=["data_optimizer"],           condition="is_micro_drama"),
    Stage("storyboard",   agents=["director"],                 parallel=["sound_narrative"]),
    Stage("visual_prompt",agents=["visual"]),
    Stage("final_check",  agents=["consistency"],              sub_task="motif_review"),
    Stage("generate",     agents=[],                           condition="phase6_ready"),
]
```

#### Agent 基础类

```python
class BaseAgent:
    name: str
    required_edition: Edition
    status: AgentStatus           # DORMANT/IDLE/RUNNING/WAITING
    event_subscriptions: list[str]
    knowledge_modules: list[str]
    circuit_breaker: CircuitBreaker

    async def run(self, task: AgentTask) -> AgentResult: ...
    async def on_event(self, event: Event): ...
    async def communicate(self, target: str, message: AgentMessage): ...
    def load_knowledge(self, module: str) -> KnowledgeModule: ...

class KnowledgeModule:
    name: str; version: str
    prompts: list[PromptTemplate]; rules: list[Rule]; checklists: list[Checklist]
```

---

## 八、系统架构

### 8.1 双平台

```
+-------------------------------------------------------------+
|  Shared Core (95% 代码共享)                                    |
|  React + TypeScript + Zustand + TipTap + Yjs + React Flow    |
+---------------------------+-----------------------------------+
|  Web (Next.js + Vercel)   |  Desktop (Tauri 2.0 + Rust)      |
|  WebSocket协作             |  本地文件 + SQLite + 离线模式     |
+---------------------------+-----------------------------------+
|  Platform Abstraction Layer                                    |
|  storage / notification / file / network                       |
+-------------------------------------------------------------+
```

### 8.2 技术栈

```
前端: React 19 / TypeScript / TailwindCSS v4 + shadcn/ui / Zustand
      TipTap + Yjs / dnd-kit / Framer Motion / Recharts
      @xyflow/react v12 (节点画布) / Three.js (Cinema Lab 3D, Phase 6)
Web:  Next.js 15 / Hocuspocus / Vercel or Docker
桌面: Tauri 2.0 / Rust / SQLite
后端: Python FastAPI / Anthropic SDK / Celery + Redis / Hocuspocus
数据: PostgreSQL / SQLite(桌面+开发期) / Redis / S3-MinIO
知识库: YAML/MD → KnowledgeModule加载器 + 热加载(Ultimate)
布局算法: ELK.js / dagre (节点自动布局)
i18n: next-intl (localePrefix: 'as-needed', 中文默认无前缀)
```

### 8.3 团队协同

```
实时同步: Yjs (CRDT) + Hocuspocus + TipTap协作 + 画布节点位置同步
权限: Owner / Editor / Commenter / Viewer
功能: 多人光标 / 行内评论 / 任务指派 / 审批流 / 活动流
```

### 8.4 目录结构

```
unrealmake/
├── packages/
│   ├── shared/                      # 共享核心 95%
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn
│   │   │   ├── canvas/              # 节点画布模块
│   │   │   │   ├── CanvasWorkspace.tsx
│   │   │   │   ├── NodeLibrary.tsx
│   │   │   │   ├── NodeProperties.tsx
│   │   │   │   ├── CanvasMinimap.tsx
│   │   │   │   ├── CanvasToolbar.tsx
│   │   │   │   ├── TemplateSelector.tsx
│   │   │   │   ├── PipelineRunner.tsx
│   │   │   │   ├── nodes/           # BaseNode + 各类型节点 (~25个)
│   │   │   │   ├── edges/           # FlowEdge / MonitorEdge / ConflictEdge
│   │   │   │   └── hooks/           # useCanvasStore / useNodeExecution / usePipelineRunner
│   │   │   ├── cinema-lab/          # Cinema Lab模块
│   │   │   │   ├── CinemaLabPanel.tsx
│   │   │   │   ├── LensCombo.tsx
│   │   │   │   ├── CameraManipulator.tsx
│   │   │   │   ├── LightingSetup.tsx
│   │   │   │   ├── MotionPoseControl.tsx
│   │   │   │   └── hooks/
│   │   │   ├── assets/              # 资产库模块(三级跨项目可复用)
│   │   │   │   ├── AssetLibraryPanel.tsx   # 资产浏览/搜索/筛选
│   │   │   │   ├── AssetCard.tsx           # 资产卡片(缩略图+类型+scope)
│   │   │   │   ├── AssetEditor.tsx         # 资产编辑(提示词/图片/视频内容)
│   │   │   │   ├── AssetPreview.tsx        # 资产详情预览
│   │   │   │   ├── ProjectAssetRefPanel.tsx # 项目引用管理(覆盖/锁定)
│   │   │   │   ├── AssetMarketplace.tsx    # 公用资产市场(官方+社区)
│   │   │   │   ├── AssetRegenerator.tsx    # AI重生成面板
│   │   │   │   └── hooks/
│   │   │   ├── capcut/              # 剪映工程包模块
│   │   │   │   ├── CapCutDraftPanel.tsx
│   │   │   │   ├── TimelinePreview.tsx
│   │   │   │   ├── DirectorNotesEditor.tsx
│   │   │   │   └── hooks/
│   │   │   ├── marketing/           # 宣发物料模块
│   │   │   │   ├── CoverGenerator.tsx
│   │   │   │   ├── PosterGenerator.tsx
│   │   │   │   └── TrailerDraftPanel.tsx
│   │   │   ├── marketplace/         # Flow Marketplace
│   │   │   │   ├── MarketplaceHome.tsx
│   │   │   │   ├── WorkflowCard.tsx
│   │   │   │   ├── WorkflowViewer.tsx
│   │   │   │   └── hooks/
│   │   │   ├── editors/             # ScriptEditor, BeatEditor, ShotCard, Timeline
│   │   │   ├── panels/             # AIAssistant, AgentMonitor, TensionCurve,
│   │   │   │                        # SoundNarrative, MotifTracker, Comments
│   │   │   ├── workspace/           # Canvas, PanelLayout, Minimap
│   │   │   ├── wizard/              # StepNav, WizardLayout
│   │   │   ├── import/              # NovelImport, ScriptImport, AdaptationReport
│   │   │   └── cards/
│   │   ├── stores/                  # project, editor, agent, collab, edition, canvas
│   │   ├── hooks/                   # useAgent, useCollaboration, useEdition, useKnowledge
│   │   ├── lib/                     # api, featureFlags, platform
│   │   └── types/
│   ├── web/                         # Next.js
│   └── desktop/                     # Tauri
│
├── backend/
│   ├── main.py
│   ├── api/
│   │   ├── projects.py
│   │   ├── import_novel.py / import_script.py
│   │   ├── script_adaptation.py
│   │   ├── knowledge.py
│   │   ├── beats.py / script.py / storyboard.py
│   │   ├── ai_operations.py
│   │   ├── canvas.py                # 画布CRUD + 节点执行
│   │   ├── marketplace.py           # 工作流社区
│   │   ├── cinema_lab.py            # Cinema Lab API
│   │   ├── assets.py               # 资产库CRUD+搜索+三级scope管理API
│   │   ├── capcut_export.py         # 剪映工程包导出
│   │   ├── marketing.py             # 宣发物料生成
│   │   ├── ai_music.py              # AI音乐生成
│   │   ├── templates.py             # 工作流模板
│   │   ├── collaboration.py / teams.py
│   │   ├── data_feedback.py
│   │   └── export.py
│   ├── agents/
│   │   ├── base.py                  # BaseAgent + KnowledgeModule
│   │   ├── bus.py                   # AgentBus
│   │   ├── coordinator.py / analyst.py / consistency.py
│   │   ├── screenwriter.py / micro_drama_writer.py
│   │   ├── director.py / visual_prompt.py
│   │   ├── reviewer.py / data_optimizer.py
│   │   └── registry.py
│   ├── knowledge/
│   │   ├── loader.py
│   │   ├── hot_reload.py
│   │   └── modules/                 # ~15个YAML/MD知识库模块
│   │       ├── director_core.yaml / director_advanced.yaml
│   │       ├── visual_design.yaml
│   │       ├── sequence_designers/  # 5个
│   │       ├── origin_screenwriter/ # 原点10专家
│   │       ├── micro_drama/         # 11节点
│   │       ├── cinema_lab.yaml      # Cinema Lab知识库
│   │       ├── sound_narrative.yaml / mise_en_scene.yaml
│   │       ├── visual_motif.yaml / tension_dynamics.yaml
│   │       ├── cultural_visual.yaml / nonlinear_narrative.yaml
│   │       ├── theme_archaeology.yaml / script_adaptation.yaml
│   │       ├── thrill_visual_linkage.yaml / ip_extension.yaml
│   │       ├── asset_generation.yaml   # 资产生成知识库
│   │       ├── color_script.yaml       # 色彩剧本知识库
│   │       ├── capcut_integration.yaml # 剪映对接知识库
│   │       ├── marketing_assets.yaml   # 宣发物料知识库
│   │       └── data_patterns/
│   ├── services/
│   │   ├── ai_engine.py             # 统一LLM调用层
│   │   ├── novel_parser.py / script_parser.py / script_adapter.py
│   │   ├── tension_engine.py / collab_service.py / export_service.py
│   │   └── node_execution.py        # 节点执行→Agent任务映射
│   ├── prompts/
│   ├── models/
│   └── config.py
│
├── knowledge-base/                  # 原始知识库Markdown
├── infra/
├── docs/
├── turbo.json
└── pnpm-workspace.yaml
```

### 8.5 数据模型

```
=== 核心业务 ===
Project (import_source: novel/script/blank)
  → [小说] Chapter → Beat → Scene → Shot → VisualPrompt
  → [剧本] ScriptAdaptationReport → Scene → Shot → VisualPrompt
  → KnowledgeBase → Character / Location / WorldBuilding / StyleGuide
  → Asset (scope: official/shared/personal/project) → AssetContent (prompt/image/video/json)
  → ProjectAssetRef (项目引用+覆盖+锁定)

Shot 扩展字段:
  + sound_narrative JSONB        (声音叙事)
  + mise_en_scene JSONB          (场面调度)
  + cinema_lab JSONB             (Cinema Lab配置)
  + tension_score DECIMAL        (张力值)
  + visual_motifs JSONB          (命中的视觉母题)
  + cultural_preset VARCHAR      (文化视觉预设)
  + thrill_type VARCHAR          (爽点类型, 微短剧)
  + thrill_visual_strategy JSONB (爽点视觉增强)

=== 资产库 (跨项目三级可复用) ===
Asset (id, owner_id, scope: official/shared/personal/project,
       project_id?, type: character/prop/location/lighting/motion/style/generic,
       name, description, tags[], thumbnail?, source_asset_id?,
       knowledge_ref?: {type, id})
AssetContent (asset_id, format: prompt/image/video/json,
              label, url?, text?, metadata JSONB)
ProjectAssetRef (project_id, asset_id, overrides JSONB?,
                 locked BOOLEAN, role VARCHAR)
AssetSharing (asset_id, price DECIMAL, permission: preview/reference/download,
              download_count, revenue DECIMAL)

=== 画布 ===
WorkflowCanvas (project_id, nodes JSONB, edges JSONB, viewport JSONB,
                is_public, public_slug, clone_count)
NodeExecution (canvas_id, node_id, node_type, status, progress,
              input/output_snapshot, agent_task_id, tokens_used, model_used)

=== Marketplace ===
MarketplaceWorkflow (slug, creator_id, name, category, tags[],
                     required_edition, nodes JSONB, edges JSONB,
                     preview_images[], clone_count, rating, forked_from)

=== 协作 ===
Team, Comment, Activity

=== Agent ===
AgentTask, AgentMemory, KnowledgeModuleVersion

=== 数据反馈 ===
PerformanceData, ContentPattern, PlatformInsight

=== 剪映+宣发 ===
CapCutExport (project_id, version, config JSONB, director_notes JSONB,
              total_duration_ms, shot_count, export_path)
MarketingAsset (project_id, type, variant, config JSONB, output_url)
```

---

## 九、UI/UX 设计体系

### 9.1 设计原则

```
1. Hierarchy: 内容至上, 控件半透明/模糊材质, 节点画布为核心视觉焦点
2. Harmony: Web=桌面视觉一致, 圆角/间距对齐, spring物理缓动
3. Consistency: 所有版本同一组件库, 相同操作同一交互, Dark/Light自动适配
4. Content-Driven: 画布区域>=70%, 所有面板可折叠, AI结果嵌入节点
```

### 9.2 视觉规范

```
=== 色彩 ===
Dark (默认):
  Level 0: #0a0a1a | Level 1: #12122a | Level 2: #1a1a36 | Level 3: #242450
  Glass: blur(20px) saturate(180%) + rgba(255,255,255,0.05~0.08) + border rgba(255,255,255,0.08)
  强调: #6366f1 (Indigo) | 暖金: #e2b714 | 渐变: 135deg #6366f1→#8b5cf6
  语义: 成功#22c55e | 警告#f59e0b | 错误#ef4444 | 信息#3b82f6
  Agent: 运行#3b82f6+pulse | 完成#22c55e | 等待#6b7280 | 错误#ef4444 | 锁定#374151+lock

Light:
  背景: #fafafa→#ffffff→#f5f5f5 | Glass: bg rgba(255,255,255,0.7) | 文字: #1a1a2e

=== 字体 ===
中文: "Noto Sans SC", system-ui | 英文: "Inter", system-ui | 等宽: "JetBrains Mono"
字号: xs:11 sm:13 base:15 lg:17 xl:20 2xl:24 3xl:30 (px)
行高: 1.5(正文) / 1.3(标题) / 1.8(剧本) | 中文: letter-spacing 0.02em

=== 间距/圆角 ===
间距(4px基准): xs:4 sm:8 md:12 lg:16 xl:24 2xl:32 3xl:48
圆角: sm:6 md:8 lg:12 xl:16 full:9999

=== 阴影/边框 ===
Dark: 卡片 1px rgba(255,255,255,0.06) | 浮动 +shadow 0 8px 32px rgba(0,0,0,0.5)
聚焦: ring 2px #6366f1

=== 动画 ===
Framer Motion | spring({stiffness:300, damping:30}) | 退出 ease-out 200ms
微交互: 100-150ms | 面板: 200-300ms | 页面: 300-400ms | Agent: 500ms
prefers-reduced-motion: 禁用弹性, 改为fade
```

### 9.3 组件规范

```
按钮: 高度36/44px | 圆角8px | Primary品牌渐变 | hover亮度+10% | disabled opacity 0.5
卡片: Level 1背景 | 12px圆角 | 16px内边距 | hover边框变亮+上移2px
导航栏: 48px高 Glass | 左Logo+项目名 | 中阶段Tab | 右团队+设置
编辑器: TipTap 等宽15px 行距1.8 | 场景标题大写加粗 | AI浮动工具栏Glass
Sheet: HIG Sheet 16px圆角 | 关闭: X+ESC+背景+下滑
Toast: 右上角Glass | 3s(成功)/5s(警告)/手动(错误)
```

### 9.4 页面布局

#### 普通版向导式
```
+--------------------------------------------------------------+
|  [Glass Nav] 虚幻造物                           [设置][头像]  |
+--------------------------------------------------------------+
|  创建新项目                                                   |
|  +---------------------+    +---------------------+          |
|  | 从小说开始           |    | 从剧本开始           |          |
|  | [品牌渐变按钮]       |    | [品牌渐变按钮]       |          |
|  +---------------------+    +---------------------+          |
|  [导入] → [知识库] → [节拍] → [剧本] → [分镜]                |
|  [← 上一步]                         [下一步 →]              |
+--------------------------------------------------------------+
```

Normal 版画布为**向导式锁定工作流**: 节点按预设排布，不可自由拖动，当前步骤高亮。

#### 画布版工作台
```
+----------------------------------------------------------------------+
| [Glass Nav] 虚幻造物 | 项目名 | 节点库 | Run全链路 | 分享Flow链接     |
+----------+-------------------------------------------+-------------------+
| 节点库    |             主节点画布                     |  属性面板         |
| (拖拽)    |  (连线+嵌入预览+实时日志)                   |  (Cinema Lab控件) |
|           |  [Prompt]──[导演]──[视觉]                  |  Lens/Lighting等  |
|           |  每个节点显示缩略+状态灯                     |                   |
+----------+-------------------------------------------+-------------------+
```

#### 分镜网格 (双击导演节点展开)
```
+----------------------------------------------------------------------+
| 分镜编辑器 — 场景: INT.书房-夜                   [返回画布]            |
+----------+-------------------------------------------+-------------------+
| 场景导航  |  分镜网格 (2/3/4列自适应)                  |  属性+Cinema Lab  |
|          |  [Shot001][Shot002][Shot003]                |  Lens/Camera/Light |
|          |  [Shot004][Shot005][Shot006]                |  声音叙事         |
|          |  时间轴(底部) + 对应剧本(可折叠)             |  视觉Prompt       |
+----------------------------------------------------------------------+
```

#### 调试面板 (Ultimate, Cmd+`)
```
+--------------------------------------------------------------+
| Debug Panel                                                    |
+----------------+--------------------+----------------------------+
| Agent日志       | Prompt日志          | 知识库+数据反馈            |
| 导演 Step 4/7  | Input: 2800 tok    | 模型: opus-4-6            |
| 序列: 对白      | Output: 1200 tok   | 张力: 72/100              |
+----------------+--------------------+----------------------------+
```

### 9.5 无障碍 (HIG)

- 键盘导航: Tab顺序 + 所有功能可键盘完成
- 焦点环: 2px 品牌色 Focus Ring
- 颜色对比: >=4.5:1 (AA) / 重要>=7:1 (AAA)
- 不依赖颜色: Agent状态有文字+图标
- Reduced Motion: 禁用弹性, 改fade
- 字体缩放: rem单位
- aria-label / alt / role
- 高对比模式: 边框加粗, 背景纯色化

### 9.6 响应式

```
断点: sm:640 md:768 lg:1024 xl:1280 2xl:1536 (px)
桌面: 全屏/分屏, 缩小时自动折叠面板, 最小800x600
面板记忆: 宽度/折叠状态持久化
```

---

## 十、页面路由

```
/                                   → 首页/登录
/marketplace                        → Flow Marketplace
/marketplace/view/{slug}            → 工作流只读预览
/projects                           → 项目列表
/projects/new                       → 新建项目(选择模板)
/projects/{id}                      → 项目画布(主工作区)
/assets                             → 我的资产库(自用+项目)
/assets/marketplace                 → 公用资产市场(官方+社区)
/projects/{id}/assets               → 项目资产引用管理
/projects/{id}/cinema-lab/{shot_id} → Cinema Lab全屏
/projects/{id}/capcut-preview       → 剪映工程包预览
/projects/{id}/marketing            → 宣发物料中心
/projects/{id}/export               → 导出中心
/settings                           → 用户设置
/settings/edition                   → 版本升级
/admin/debug                        → 调试面板 (Ultimate)
```

---

## 十一、Prompt 优先级

### MVP (Phase 1-2)

| 优先级 | ID | 名称 | 模型 | 温度 |
|--------|----|------|------|------|
| P0 | P01 | 章节分割 | Haiku | 0.2 |
| P0 | P03 | 角色提取 | Sonnet | 0.4 |
| P0 | P10 | 小说→Beat | Sonnet | 0.5 |
| P0 | P11 | Beat→场景 | Sonnet | 0.5 |
| P0 | PS01 | 剧本格式解析 | Haiku | 0.2 |
| P0 | PS02 | 剧本逆向Beat | Sonnet | 0.4 |
| P0 | PS03 | 剧本知识库构建 | Sonnet | 0.4 |
| P1 | PS04 | 分镜可执行性评估 | Sonnet | 0.3 |
| P1 | PS05 | 剧本适配优化 | Sonnet | 0.6 |
| P1 | P04 | 角色档案深化 | Sonnet | 0.5 |
| P1 | P12 | 文本改写 | Sonnet | 0.5 |
| P1 | P22 | 场景→分镜 | Sonnet | 0.4 |
| P1 | P26 | 视觉Prompt | Sonnet | 0.5 |

### Agent 阶段 (Phase 3)

| 类别 | Prompt来源 |
|------|-----------|
| 编剧子专家 | 原点10专家 + 增强4专家 |
| 导演 | 7步 + 5序列 + 声音 + 调度 + 文化 |
| Cinema Lab | CL01-CL05 |
| 张力引擎 | tension_dynamics模块 |
| 视觉母题 | visual_motif模块 |
| 视觉Prompt | 9模块 + 爽点联动 |
| 微短剧 | 11节点 + 数据模式 |

---

## 十二、开发规范

### Monorepo
- pnpm + Turborepo, `@unrealmake/shared` 引用

### 前端
- React函数式 + TS strict / Zustand + React Query / TailwindCSS + Framer Motion
- `useEdition()` hook 控制版本差异 — 版本门控统一收敛到 Next.js middleware 路由拦截 + Canvas 节点列表过滤（仅这2处）
- 节点画布: React Flow 自定义节点, 输入/输出端口类型校验
- 类型安全: OpenAPI → TypeScript codegen（Pydantic models → openapi.json → api.generated.ts, CI 自动校验）

### 后端
- FastAPI / AI统一走 `ai_engine.py`（provider 抽象层: anthropic/openai/deepseek 可切换）/ Agent基于 `base.py`
- 知识库通过 `knowledge/loader.py` + 热加载
- 节点执行通过 `node_execution.py` 映射到Agent任务
- 版本门控: FastAPI Depends 统一拦截，业务代码零 edition 判断

### 知识库规范
- 模块: YAML(结构) + MD(Prompt内容)
- 声明: name, version, edition_required, prompts[], rules[], checklists[]
- 热加载: Ultimate版运行时修改

### Git
- `main` / `dev` / `feature/Px.x-desc`
- `feat(module): desc` / `fix(module): desc`

---

## 十三、已有资产

### 知识库文件
```
知识库/CC Skills — 导演分镜/ (core.md + advanced.md)
知识库/CC Skills — 镜头画面设计/ (advanced.md + README.md)
知识库/CC Skillsssss — 镜头序列设计/ (5个.SKILL.md + README.md)
知识库/原点编剧系统 V2.3/ (V2.0.md + 3模块.md + 8个@专家.md)
知识库/自用版/微短剧AI辅助编剧系统/ (00-11节点.txt + 改编方法论.txt)
```

### 外部资产
- PS Agent: `E:/小说转剧本/软件系统/ps_agent/` (Phase 6集成)

### 关键决策
- 暗色主题默认, Dark/Light自动适配
- MVP先Web, 桌面端Phase 5
- 知识库分层加载 (core/advanced/full)
- 双入口: 小说 + 剧本
- Phase 0 起直接用 PostgreSQL (Docker Compose), 跳过 SQLite 阶段
- Claude API Key: Ultimate设置页, 其他后端统一
- 桌面端: Win + Mac (Tauri 2.0)
- i18n: next-intl, localePrefix 'as-needed', 中文默认无前缀
- **资产库 = 跨项目可复用素材系统(角色/道具/场景/光线/动作/风格), 三级scope(官方公用免费+社区分享付费 / 自用跨项目 / 项目内), 项目引用时可覆盖+锁定, 锁定后成为下游视觉Prompt的强制锚点**
- **后期制作(剪辑/调色/音效/混音)交给剪映, 系统输出剪映工程包(Draft)**
- **PS Agent移除, 后期处理能力由剪映承担**
- **AI音乐(Suno/Udio)替代纯标注, 实现声音叙事→可用音频的转化**
 
---

## 三段式产品形态补充 2026-03-06

- 当前规划主版本已切换为 `newplan3.md`；`newplan1.md` 与 `newplan2.md` 保留为历史演进文档。
- 产品主交互采用三段式：前半段为 `Sudowrite` 式创作工作台；中段为 `Tapnow/TapFlow` 式可执行无限画布工作台，并吸收 `Figma/Miro` 的协作优势；后半段为 `Premiere/CapCut` 式预演与交付工作台。
- `newplan3.md` 的核心意义，是在不删除 `newplan1.md` 细部模型、接口、页面、附录内容的前提下，完成对三段式、四层用户群体版本体系、Tapnow 中段判断与渐进开发路线的融合重构。
- 四层用户群体版本体系正式表述为：`Normal` 入口层、`Canvas` 生产层、`Hidden` 方案层、`Ultimate` 内部操作系统层。
- `Normal` 以前半段与简化后半段为主；`Canvas` 完整使用三段式且以中段为主力生产台；`Hidden` 开放更高阶策略能力；`Ultimate` 承载实验、调试、评测与数据闭环。
- 中段默认不应作为空白自由白板使用，而应以模板工作流、推荐路径、结果摘要卡、局部重跑和显式回写为默认体验。
- 规划、里程碑与工程映射请以 `newplan3.md` 为主；终局架构和 KPI 参见 `FINAL_ROADMAP.md`；三段式页面形态详见 `docs/TRI_STAGE_CREATIVE_UX.md`。
