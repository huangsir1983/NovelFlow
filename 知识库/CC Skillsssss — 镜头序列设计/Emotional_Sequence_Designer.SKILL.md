# Skill: 情感戏镜头序列设计

## 基本信息

- **name**: Emotional_Sequence_Designer
- **版本**: v1.0
- **作者**: 猫叔
- **description**: AI视频情感场景分镜设计
- **关联Skill**: 导演分镜系统、镜头画面设计、对话场景镜头序列

## 痛点与解决方案

### 痛点
- 镜头过于直白，缺乏情感层次
- 节奏单一，无法体现情绪起伏
- 特写滥用，失去情感冲击力
- 缺乏留白，观众没有感受空间

### 解决方案
涵盖爱情、悲伤、冲突三大情感场景，通过细腻的镜头语言和节奏控制，让AI情感视频真正打动人心。基于经典爱情片、剧情片剪辑语法，支持单人情绪到多人互动的扩展，内置情绪弧线自动匹配系统。

## 核心能力

| 能力模块 | 功能描述 | 适用场景 |
|---------|---------|---------|
| 爱情镜头系统 | 亲密感营造的镜头语法 | 浪漫、暧昧、表白场景 |
| 悲伤镜头系统 | 情绪渲染的镜头策略 | 失落、离别、哀悼场景 |
| 冲突镜头系统 | 张力积累的镜头技巧 | 争吵、对峙、决裂场景 |
| 情绪节奏引擎 | 根据情感曲线调整镜头 | 全场景适用 |
| 留白与呼吸 | 创造情感空间的技巧 | 情绪高潮/转折处 |

## 核心功能

### 1. 爱情镜头系统 (Romance_Sequence)

#### 亲密感营造

```yaml
Romance_Sequence:
  description: "爱情场景的镜头语法"

  intimacy_building:
    stages:
      - stage: "Attraction"
        shots:
          - type: "Glance_Shot"
            description: "偷看对方的眼神"
            duration: "2-3s"

          - type: "Reaction_to_Glance"
            description: "被发现后的反应"
            duration: "1-2s"

          - type: "Shared_Moment"
            description: "两人同框，但保持距离"
            duration: "3-5s"

      - stage: "Connection"
        shots:
          - type: "Close_Proximity"
            description: "两人距离拉近"
            duration: "4-6s"

          - type: "Eye_Contact"
            description: "深情对视"
            duration: "3-5s"
            camera: "缓慢推进"

          - type: "Touch_Setup"
            description: "即将触碰的期待"
            duration: "2-4s"

      - stage: "Intimacy"
        shots:
          - type: "First_Touch"
            description: "第一次触碰"
            duration: "3-5s"
            technique: "慢动作或特写"

          - type: "Embrace"
            description: "拥抱"
            duration: "5-8s"

          - type: "Kiss_Sequence"
            description: "亲吻镜头组"
            shots:
              - "Face_Close_Up - 双方表情"
              - "Profile_Two_Shot - 侧脸双人"
              - "Close_Up_Lips - 唇部特写"
              - "Pull_Back - 拉开展示环境"

  romantic_composition:
    - "浅景深，虚化背景突出人物"
    - "柔和光线，金色时刻最佳"
    - "框架构图（门窗、树枝等）"
    - "反射元素（水面、镜子）"
```

#### 爱情镜头类型库

```yaml
Romance_Shot_Types:
  glances:
    - name: "Stolen_Look"
      description: "偷看"
      duration: "1-2s"

    - name: "Caught_Looking"
      description: "被发现"
      duration: "1-2s"
      expression: "害羞/尴尬"

    - name: "Longing_Gaze"
      description: "渴望的眼神"
      duration: "3-5s"

  proximity:
    - name: "Close_Standing"
      description: "近距离站立"
      framing: "两人占画面大部分"

    - name: "Almost_Touching"
      description: "即将触碰"
      tension: "高"

    - name: "Accidental_Touch"
      description: "意外触碰"
      reaction: "双方反应"

  intimate:
    - name: "Hand_Holding"
      description: "牵手"
      close_up: true

    - name: "Caress"
      description: "抚摸"
      slow_motion: "可选"

    - name: "Forehead_Touch"
      description: "额头相抵"
      emotional_peak: true
```

### 2. 悲伤镜头系统 (Grief_Sequence)

#### 悲伤渲染策略

```yaml
Grief_Sequence:
  description: "悲伤场景的镜头策略"

  grief_stages:
    - stage: "Shock"
      shots:
        - type: "Wide_Empty"
          description: "人物在空旷环境中显得渺小"
          duration: "3-5s"

        - type: "Frozen_Expression"
          description: "震惊的表情特写"
          duration: "2-4s"

    - stage: "Processing"
      shots:
        - type: "Looking_Away"
          description: "看向远方，眼神空洞"
          duration: "4-6s"

        - type: "Object_Focus"
          description: "聚焦触发回忆的物品"
          duration: "3-5s"

        - type: "Environment_Reaction"
          description: "环境衬托（雨、阴天等）"
          duration: "3-5s"

    - stage: "Release"
      shots:
        - type: "Tear_Close_Up"
          description: "眼泪特写"
          duration: "3-5s"

        - type: "Breakdown"
          description: "情绪崩溃"
          duration: "5-10s"
          camera: "稳定，让表演说话"

        - type: "Comfort"
          description: "被安慰（如有）"
          duration: "5-8s"

  visual_metaphors:
    - "下雨 - 泪水外化"
    - "落叶 - 失去"
    - "空椅子 - 缺席"
    - "褪色照片 - 回忆"
    - "关闭的门 - 终结"
```

### 3. 冲突镜头系统 (Conflict_Sequence)

#### 张力积累技巧

```yaml
Conflict_Sequence:
  description: "冲突场景的镜头技巧"

  tension_building:
    phases:
      - phase: "Setup"
        shots:
          - type: "Wide_Tension"
            description: "两人距离较远，空间紧张"
            duration: "3-5s"

          - type: "Alternating_Close_Ups"
            description: "交替特写，情绪对比"
            duration: "各2-3s"

      - phase: "Escalation"
        shots:
          - type: "Moving_Closer"
            description: "双方逐渐靠近"
            duration: "4-6s"

          - type: "Quick_Cuts"
            description: "快速剪辑增加紧张"
            duration: "各1-2s"

          - type: "Voice_Rising"
            description: "声音提高时的特写"
            duration: "2-3s"

      - phase: "Climax"
        shots:
          - type: "Face_to_Face"
            description: "面对面特写"
            duration: "3-5s"

          - type: "Angry_Gesture"
            description: "愤怒手势特写"
            duration: "1-2s"

          - type: "Silence_After_Storm"
            description: "争吵后的沉默"
            duration: "4-6s"

  conflict_techniques:
    - "Dutch angle增加不稳定感"
    - "推轨变焦（Vertigo效果）"
    - "色彩对比（冷暖对比）"
    - "空间压缩（长焦）"
```

### 4. 情绪节奏引擎 (Emotional_Rhythm)

#### 情绪弧线匹配

```yaml
Emotional_Rhythm:
  description: "根据情绪曲线调整镜头节奏"

  arc_patterns:
    rising:
      description: "情绪上升"
      shot_duration: "逐渐缩短"
      camera_movement: "增加"
      music: "渐强"

    peak:
      description: "情绪高峰"
      shot_duration: "延长"
      camera: "稳定或极慢推进"
      music: "最强或突然静止"

    falling:
      description: "情绪回落"
      shot_duration: "逐渐延长"
      camera_movement: "减少"
      music: "渐弱"

    resolution:
      description: "情绪解决"
      shot_duration: "较长，稳定"
      camera: "静止或缓慢拉远"
      music: "平静"

  breathing_moments:
    - "情绪转折后留白2-3秒"
    - "高潮后给恢复时间"
    - "重要台词后停顿"
```

### 5. 留白与呼吸 (Negative_Space)

#### 情感空间创造

```yaml
Negative_Space:
  description: "创造情感空间的技巧"

  techniques:
    - name: "Empty_Frame"
      description: "空镜头过渡"
      duration: "2-4s"
      use_case: "情绪转折、时间流逝"

    - name: "Long_Hold"
      description: "长镜头停留"
      duration: "5-10s或更长"
      use_case: "让观众感受情绪"

    - name: "Off_Screen_Sound"
      description: "画外音/声音延续"
      use_case: "声音先于画面或延续"

    - name: "Reflection_Shot"
      description: "反射镜头"
      use_case: "增加层次，暗示内心"

  composition:
    - "大量留白，人物偏于一侧"
    - "低饱和度色彩"
    - "自然光线，避免人工感"
    - "环境音保留"
```

## 使用示例

### 示例1：初次表白

**场景**：黄昏公园长椅
**情绪**：紧张、期待、甜蜜

```
序列设计：
1.  [4s] Wide     - 公园黄昏，两人坐在长椅两端（距离）
2.  [3s] Medium   - 男主偷看女主，女主看远方
3.  [2s] Close    - 女主侧脸，夕阳映照
4.  [2s] Close    - 男主鼓起勇气
5.  [3s] Medium   - 男主向女主挪动
6.  [4s] Close    - 两人眼神相遇
7.  [3s] Close    - 男主手慢慢靠近女主的手
8.  [5s] Close    - 两只手触碰（慢动作）
9.  [4s] Two_Shot - 两人微笑
10. [6s] Wide     - 夕阳下的剪影（拉远）
```

### 示例2：得知噩耗

**场景**：医院走廊
**情绪**：震惊、难以置信、崩溃

```
序列设计：
1.  [5s] Wide   - 空旷走廊，主角站在医生面前显得渺小
2.  [4s] Close  - 主角听到消息后的表情凝固
3.  [3s] Close  - 医生说话的嘴（画外音）
4.  [5s] Close  - 主角眼神空洞，焦点虚掉
5.  [4s] Medium - 主角扶墙，身体下滑
6.  [3s] Close  - 墙壁上的医院标志（失焦）
7.  [6s] Close  - 主角眼泪滑落
8.  [8s] Medium - 主角蹲下抱头
9.  [5s] Wide   - 走廊尽头窗户，外面下雨
10. [6s] Close  - 主角颤抖的肩膀
```

### 示例3：情侣决裂

**场景**：公寓客厅
**情绪**：愤怒、受伤、绝望

```
序列设计：
1.  [4s] Wide   - 客厅，两人分站两侧
2.  [3s] Close  - A愤怒的表情
3.  [3s] Close  - B受伤的眼神
4.  [2s] Close  - A提高音量
5.  [2s] Close  - B后退一步
6.  [3s] Medium - A走向B
7.  [2s] Close  - B摇头
8.  [4s] Close  - 两人面对面，剑拔弩张
9.  [3s] Close  - A说出决绝的话
10. [5s] Close  - B眼泪涌出，但强忍
11. [4s] Medium - B转身离开
12. [6s] Wide   - A独自站在空荡客厅
13. [5s] Empty  - 门关上的空镜头
```

## 详细示例：表白场景完整分镜

**场景设定**：
- 地点：秋日公园长椅
- 时间：黄昏，金色时刻
- 人物：男主角（紧张）、女主角（温柔）
- 情绪：紧张→期待→甜蜜

**完整镜头序列**：

| 镜号 | 镜头类型 | 景别 | 时长 | 画面描述 | AI提示词要点 |
|-----|---------|------|-----|---------|-------------|
| 1 | Wide | 全景 | 4s | 公园黄昏，两人坐在长椅两端，距离明显 | autumn park, golden hour, couple on bench, distance between them, warm lighting |
| 2 | Medium | 中景 | 3s | 男主偷看女主，女主望向远方 | man glancing at woman, woman looking away, anticipation |
| 3 | Close | 特写 | 2s | 女主侧脸，夕阳映照，发丝发光 | woman profile, golden hour lighting, hair glowing, soft focus |
| 4 | Close | 特写 | 2s | 男主鼓起勇气，喉结滚动 | man gathering courage, nervous, throat moving |
| 5 | Medium | 中景 | 3s | 男主向女主方向挪动 | man moving closer on bench, subtle movement |
| 6 | Close | 特写 | 4s | 两人眼神相遇，时间仿佛静止 | eye contact, intimate moment, shallow depth of field |
| 7 | Close | 特写 | 3s | 男主手慢慢靠近女主的手 | hand reaching, almost touching, anticipation |
| 8 | Close | 特写 | 5s | 两只手触碰（慢动作效果） | hands touching, slow motion feel, emotional moment |
| 9 | Two_Shot | 双人 | 4s | 两人相视微笑，距离消失 | two shot, smiling at each other, connection |
| 10 | Wide | 全景 | 6s | 夕阳下的剪影，镜头缓缓拉远 | silhouette, golden hour, pulling back, romantic atmosphere |

## 与现有Skill对接

### 对接对话场景镜头序列

```yaml
integration:
  emotional_dialogue:
    base: "对话场景镜头序列Skill"
    enhancement: "情感戏Skill增加情绪层次"
    combination: "对话节奏+情感渲染"
```

- 情感戏往往包含对话，两个Skill可以叠加使用
- 情感戏Skill负责情绪渲染，对话Skill负责节奏控制

### 对接镜头画面设计

```yaml
emotional_visuals:
  color_grading:
    - "爱情：暖色调，高饱和"
    - "悲伤：冷色调，低饱和"
    - "冲突：高对比，冷暖对比"

  lighting:
    - "爱情：柔和，逆光"
    - "悲伤：阴暗，单一光源"
    - "冲突：硬朗，强烈阴影"
```

### 对接导演分镜系统

- 情感戏需要更细腻的分镜标注，包括：情绪指示、节奏标记、留白提示

## 提示词模板

### 基础提示词

```
你是一个情感戏分镜专家。请为以下场景设计镜头序列：

场景类型：[爱情/悲伤/冲突]
场景描述：
[详细描述]

情绪弧线：
[如：紧张→期待→甜蜜]

请输出：
1. 情绪曲线图
2. 完整镜头序列
3. 每个镜头的AI绘画提示词
4. 节奏建议
```

### 高级提示词

```
作为电影情感戏分镜大师，请为以下场景设计细腻的镜头序列：

场景：
[详细描述]

参考影片：[如：《泰坦尼克号》《蓝色情人节》等]

情感要求：
- 核心情绪：[具体情绪]
- 情绪层次：[详细描述]
- 转折点：[关键转折]

技术要求：
- 摄影风格：[如：手持、稳定器等]
- 色彩基调：[如：暖黄、冷蓝等]
- 节奏偏好：[如：舒缓、紧凑等]

请提供：
1. 情绪弧线图
2. 详细分镜表
3. 视觉隐喻建议
4. AI绘画提示词
```

## 参数速查表

| 情感类型 | 平均镜头时长 | 特写比例 | 节奏特点 |
|---------|-------------|---------|---------|
| 浪漫爱情 | 3-6s | 50% | 舒缓、流畅 |
| 暧昧紧张 | 2-4s | 40% | 时快时慢 |
| 悲伤哀悼 | 4-8s | 60% | 缓慢、沉重 |
| 激烈冲突 | 1-3s | 45% | 快速、断续 |
| 内心独白 | 5-10s | 70% | 极慢、沉思 |

## 版本记录

- v1.0 (2024-02) - 初始版本，包含爱情、悲伤、冲突三大情感系统