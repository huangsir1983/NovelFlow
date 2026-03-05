# Skill: 对话场景镜头序列设计

## 基本信息

- **name**: Dialogue_Shot_Sequence_Designer
- **版本**: v1.0
- **作者**: 猫叔
- **description**: AI视频对话场景分镜设计
- **关联Skill**: 导演分镜系统、镜头画面设计、竖屏短剧节奏优化

## 痛点与解决方案

### 痛点
- 镜头切换生硬，缺乏对话的"呼吸感"
- 正反打角度混乱，观众分不清谁在说话
- 反应镜头缺失，对话变成"念台词"
- 轴线问题导致空间感混乱

### 解决方案
通过预设的正反打系统、过肩镜头库、反应链机制和轴线管理，系统化解决对话分镜中的核心问题，让AI视频对话场景具备电影级的节奏感。

## 核心能力

| 能力模块 | 功能描述 | 适用场景 |
|---------|---------|---------|
| 正反打系统 | 自动生成180°规则内的正反打镜头组 | 双人对话场景 |
| 过肩镜头库 | 多种过肩角度选择（OTS/OTS变体） | 建立空间关系 |
| 反应链机制 | 说话者→听者反应→说话者回应的循环 | 增强对话张力 |
| 轴线管理 | 自动检测和维护轴线一致性 | 避免越轴错误 |
| 节奏控制 | 根据对话情绪调整镜头时长 | 匹配对话节奏 |

## 核心功能

### 1. 正反打镜头系统 (Shot_Reverse_Shot)

#### 基础配置

```yaml
Shot_Reverse_Shot:
  description: "经典正反打镜头序列"
  character_positions:
    A:
      position: "画面左侧，面向右"
      eyeline: "向右上方15°"
      camera_angle: "右侧45°"
    B:
      position: "画面右侧，面向左"
      eyeline: "向左上方15°"
      camera_angle: "左侧45°"

  shot_sequence:
    - shot: "Wide_Establishing"
      duration: "3-5s"
      description: "双人中景，建立空间关系"

    - shot: "SRS_A"
      type: "Medium_Close_Up"
      subject: "Character_A"
      duration: "根据台词长度"
      composition: "头部上方留1/3空间"

    - shot: "Reaction_B"
      type: "Close_Up"
      subject: "Character_B"
      duration: "1-2s"
      capture: "微表情反应"

    - shot: "SRS_B"
      type: "Medium_Close_Up"
      subject: "Character_B"
      duration: "根据台词长度"

    - shot: "Reaction_A"
      type: "Close_Up"
      subject: "Character_A"
      duration: "1-2s"
```

#### 镜头参数

| 镜头类型 | 景别 | 机位高度 | 焦距建议 | 用途 |
|---------|------|---------|---------|------|
| Wide_Establishing | 全景/中景 | 眼平 | 35mm | 建立场景 |
| SRS_A/B | 中近景 | 眼平 | 50-85mm | 主体对话 |
| Reaction | 特写 | 眼平 | 85-135mm | 情绪反应 |
| Insert | 特写 | 可变 | 50mm+ | 动作细节 |

### 2. 过肩镜头系统 (Over_The_Shoulder)

#### OTS标准配置

```yaml
OTS_Shots:
  description: "过肩镜头，增强空间存在感"

  OTS_A_on_B:
    camera_position: "A身后，偏向右侧"
    shoulder_visibility: "A的肩膀占画面左侧1/4"
    subject: "B面部，画面右侧2/3"
    focus: "B的眼睛"
    depth_of_field: "f/2.8-4，虚化前景肩膀"

  OTS_B_on_A:
    camera_position: "B身后，偏向左侧"
    shoulder_visibility: "B的肩膀占画面右侧1/4"
    subject: "A面部，画面左侧2/3"
    focus: "A的眼睛"
    depth_of_field: "f/2.8-4"

  OTS_variations:
    - name: "Clean_OTS"
      description: "无肩膀遮挡，仅保留空间暗示"
      shoulder_visibility: "最小化"

    - name: "Deep_OTS"
      description: "深过肩，强调空间纵深"
      shoulder_visibility: "占画面1/3"
      camera_distance: "更远"
```

### 3. 反应链机制 (Reaction_Chain)

#### 反应链模板

```yaml
Reaction_Chain:
  description: "对话中的反应镜头序列"

  basic_pattern:
    - trigger: "关键台词/情绪点"
    - capture: "听者反应"
    - types:
        - "Micro_expression": "微表情（0.5-1s）"
        - "Thoughtful_pause": "思考停顿（1-2s）"
        - "Emotional_response": "情绪反应（2-3s）"
        - "Action_response": "动作回应（如点头、喝水）"

  advanced_techniques:
    - name: "Delayed_Reaction"
      description: "延迟反应，增加张力"
      timing: "台词结束后0.5s再切反应"

    - name: "Pre_Lap_Reaction"
      description: "反应前置，声音延续"
      timing: "反应镜头提前，台词声音叠化"

    - name: "Double_Reaction"
      description: "双重反应链"
      sequence: "A说→B反应→A看到B反应后的反应→B回应"
```

### 4. 轴线管理系统 (Axis_Management)

#### 180°规则

```yaml
Axis_System:
  description: "维护空间一致性的轴线管理"

  master_axis:
    definition: "连接两个角色的假想线"
    rule: "摄影机必须保持在轴线一侧"

  camera_positions:
    safe_zone: "轴线一侧180°范围"
    danger_zone: "跨越轴线的位置"

  axis_breaks:
    when_allowed:
      - "有明确动机（如角色移动）"
      - "使用中性镜头过渡"
      - "时间/空间跳跃"

    neutral_shots:
      - "角色正面特写（沿轴线拍摄）"
      - "空镜头/环境镜头"
      - "物体特写"
      - "POV镜头"
```

### 5. 多人对话扩展 (Multi_Character)

#### 3-4人对话配置

```yaml
Multi_Character_Dialogue:
  description: "多人对话的镜头分配策略"

  three_person:
    pattern: "三角形站位"
    shot_rotation:
      - "双人镜头（A+B）"
      - "单人镜头（C反应）"
      - "双人镜头（B+C）"
      - "单人镜头（A反应）"
      - "三人广角（重新定位）"

  four_person:
    pattern: "分组对话"
    strategy: "将4人分为2+2，分别处理"
    master_shot: "定期回到四人全景"
```

## 使用示例

### 示例1：标准双人对话

**场景**：办公室面试
**情绪**：紧张、正式

```
序列设计：
1. [3s] Wide - 面试官与应聘者对坐，全景
2. [5s] OTS_A - 过应聘者肩膀拍面试官提问
3. [1s] Reaction_B - 应聘者紧张的表情特写
4. [4s] SRS_B - 应聘者回答，中近景
5. [2s] Reaction_A - 面试官倾听的微妙表情
6. [6s] SRS_A - 面试官追问
7. [1s] Insert - 应聘者手指敲击桌面（紧张细节）
8. [3s] SRS_B - 应聘者最后回答
```

### 示例2：激烈争吵场景

**场景**：情侣争吵
**情绪**：愤怒、激动

```
序列设计：
1. [2s] Wide - 两人对峙，空间紧张
2. [3s] SRS_A - A大声说话，画面轻微晃动
3. [0.5s] Reaction_B - B震惊的微表情
4. [2s] SRS_B - B反击，语速快
5. [1s] Reaction_A - A被激怒
6. [2s] Close_A - A特写，情绪爆发
7. [0.5s] Reaction_B - B流泪
8. [3s] SRS_B - B哽咽回应
9. [4s] Wide - 两人沉默，空间疏离
```

### 示例3：3人会议场景

**场景**：商务谈判
**人物**：甲方A、乙方B、调解人C

```
序列设计：
1. [4s] Wide - 三人围坐会议桌
2. [5s] Two_Shot_A+C - A向C陈述
3. [2s] Reaction_B - B不安的表情
4. [4s] SRS_C - C回应A
5. [1s] Reaction_A - A满意点头
6. [5s] SRS_B - B提出异议
7. [2s] Two_Shot_A+B - A和B争论
8. [3s] SRS_C - C调解
9. [4s] Wide - 三人达成共识
```

## 详细示例：面试场景完整分镜

**场景设定**：
- 地点：现代办公室
- 人物：面试官（中年男性，严肃）、应聘者（年轻女性，紧张）
- 情绪：紧张、正式、略带压迫感

**完整镜头序列**：

| 镜号 | 镜头类型 | 景别 | 时长 | 画面描述 | AI提示词要点 |
|-----|---------|------|-----|---------|-------------|
| 1 | Wide | 全景 | 4s | 两人对坐，玻璃幕墙办公室，城市背景 | modern office, two people sitting across desk, city skyline through window, professional lighting |
| 2 | OTS | 过肩 | 5s | 过应聘者肩膀拍面试官，面试官审视 | over shoulder shot, interviewer looking serious, shallow depth of field, corporate setting |
| 3 | Reaction | 特写 | 1.5s | 应聘者紧张吞咽，眼神闪躲 | close up, nervous job applicant, subtle anxiety, natural lighting |
| 4 | SRS | 中近景 | 6s | 应聘者回答问题，手势紧张 | medium close up, applicant speaking, nervous hand gestures, eye level shot |
| 5 | Reaction | 特写 | 2s | 面试官微微点头，面无表情 | close up, interviewer nodding slightly, poker face, professional |
| 6 | SRS | 中近景 | 4s | 面试官追问，身体前倾 | medium close up, interviewer leaning forward, intense questioning |
| 7 | Insert | 特写 | 1s | 应聘者手指敲击桌面 | extreme close up, fingers tapping desk, nervous tic |
| 8 | SRS | 中近景 | 5s | 应聘者深呼吸，镇定回答 | medium close up, applicant taking deep breath, regaining composure |
| 9 | Two_Shot | 双人 | 3s | 两人对视，气氛缓和 | two shot, both characters, tension easing, balanced composition |

## 与现有Skill对接

### 对接导演分镜系统

```yaml
integration:
  director_system:
    input: "剧本对话段落"
    process: "Dialogue_Shot_Sequence_Designer分析"
    output: "分镜表（含镜头序列）"

  shot_design:
    input: "本Skill生成的镜头列表"
    enhancement: "镜头画面设计Skill细化每个镜头的视觉参数"
```

- 本Skill作为导演分镜系统的**对话场景专用模块**
- 输入：剧本中的对话段落标记
- 输出：可直接导入导演分镜系统的镜头序列数据

### 对接镜头画面设计

- 本Skill提供镜头类型和序列
- 镜头画面设计Skill负责细化每个镜头的：具体构图参数、光影设置、色彩风格、AI绘画提示词优化

### 对接竖屏短剧节奏优化

```yaml
vertical_adaptation:
  adjustments:
    - "双人镜头改为上下构图"
    - "特写比例增加（竖屏更适合面部特写）"
    - "反应镜头时长缩短30%"
    - "增加快速剪辑点（每1-2秒一个切换点）"
```

## 提示词模板

### 基础提示词

```
你是一个专业的对话场景分镜师。请为以下对话设计镜头序列：

对话内容：
[粘贴对话]

要求：
1. 使用正反打系统
2. 包含适当的反应镜头
3. 维护轴线一致性
4. 情绪：[指定情绪]
5. 输出完整的镜头序列表
```

### 高级提示词

```
作为电影级对话分镜专家，请为以下场景设计镜头序列：

场景描述：
[详细场景描述]

对话内容：
[对话文本]

角色信息：
- 角色A：[性格、情绪状态]
- 角色B：[性格、情绪状态]

特殊要求：
- 情绪弧线：[如：平静→紧张→爆发→和解]
- 视觉风格：[如：手持摄影、固定机位等]
- 节奏偏好：[如：紧凑、舒缓、跳跃]

请输出：
1. 轴线示意图
2. 完整镜头序列（含时长、景别、运动）
3. 每个镜头的AI绘画提示词
4. 剪辑节奏说明
```

## 参数速查表

| 参数 | 标准对话 | 紧张对话 | 亲密对话 |
|-----|---------|---------|---------|
| 平均镜头时长 | 3-5s | 1-3s | 4-8s |
| 特写比例 | 30% | 50% | 60% |
| 反应镜头时长 | 1-2s | 0.5-1s | 2-4s |
| 焦距偏好 | 50-85mm | 35-50mm | 85-135mm |
| 轴线切换 | 保守 | 可打破 | 避免 |

## 版本记录

- v1.0 (2024-02) - 初始版本，包含基础对话镜头系统