# Skill: 动作戏镜头序列设计

## 基本信息

- **name**: Action_Sequence_Designer
- **版本**: v1.0
- **作者**: 猫叔
- **description**: AI视频动作场景分镜设计
- **关联Skill**: 导演分镜系统、镜头画面设计、竖屏短剧节奏优化

## 痛点与解决方案

### 痛点
- 镜头切换混乱，观众看不清动作
- 节奏拖沓，失去紧张感
- 空间关系模糊，不知道谁在哪里
- 缺乏冲击力，动作软绵绵

### 解决方案
涵盖打斗、追逐、爆破三大核心场景，通过科学的镜头组接和节奏控制，让AI动作视频具备好莱坞级别的视觉冲击力。基于经典动作片剪辑语法（参考《谍影重重》《疯狂的麦克斯》），支持1v1到群战的扩展。

## 核心能力

| 能力模块 | 功能描述 | 适用场景 |
|---------|---------|---------|
| 打斗镜头系统 | 攻击-反应-反击的标准化序列 | 格斗、武打场景 |
| 追逐镜头系统 | 速度感营造的空间镜头组 | 追车、跑酷场景 |
| 爆破镜头系统 | 冲击波-碎片-反应的时间轴设计 | 爆炸、破坏场景 |
| 节奏控制引擎 | 根据动作强度自动调整剪辑速度 | 全场景适用 |
| 空间定位系统 | 保持动作空间一致性的标记方法 | 复杂动作场景 |

## 核心功能

### 1. 打斗镜头系统 (Fight_Sequence)

#### 基础攻击序列

```yaml
Fight_Sequence:
  description: "标准打斗镜头序列模板"

  basic_combo:
    sequence:
      - shot: "Setup"
        type: "Wide"
        duration: "2-3s"
        purpose: "建立空间关系，展示双方位置"

      - shot: "Attack_Prep"
        type: "Medium"
        duration: "0.5-1s"
        purpose: "攻击者蓄力，观众预期"

      - shot: "Attack_Execution"
        type: "Close/Medium"
        duration: "0.3-0.5s"
        purpose: "攻击动作本身，快速剪辑"
        camera_movement: "轻微跟随"

      - shot: "Impact"
        type: "Close"
        duration: "0.2-0.3s"
        purpose: "击中瞬间，冲击感"
        effects: "轻微震动/模糊"

      - shot: "Reaction"
        type: "Medium/Close"
        duration: "0.5-1s"
        purpose: "被击中者反应"

      - shot: "Recovery"
        type: "Medium"
        duration: "1-2s"
        purpose: "恢复姿态，准备反击"

  intensity_levels:
    low:
      avg_shot_duration: "1-2s"
      camera_movement: "稳定"
      impact_emphasis: "轻微"

    medium:
      avg_shot_duration: "0.5-1s"
      camera_movement: "轻微手持感"
      impact_emphasis: "明显"

    high:
      avg_shot_duration: "0.3-0.5s"
      camera_movement: "动态跟随"
      impact_emphasis: "强烈+特效"
```

#### 打斗镜头类型库

```yaml
Fight_Shot_Types:
  wide_shots:
    - name: "Master_Wide"
      description: "全景，展示整体动作编排"
      use_case: "动作开始、结束、复杂连招"

    - name: "Tracking_Wide"
      description: "跟随移动的全景"
      use_case: "移动中的打斗"
      camera: "稳定器/轨道"

  medium_shots:
    - name: "Action_Medium"
      description: "展示攻击动作的中景"
      framing: "腰部以上，保留手臂动作空间"

    - name: "Duel_Medium"
      description: "双人同框，展示攻防互动"
      use_case: "势均力敌的对决"

  close_ups:
    - name: "Impact_Close"
      description: "击中瞬间特写"
      framing: "面部或身体被击中部位"
      duration: "极短（3-6帧）"

    - name: "Intensity_Close"
      description: "战斗表情特写"
      use_case: "展示决心、痛苦、愤怒"

  pov_shots:
    - name: "Attacker_POV"
      description: "攻击者视角"
      use_case: "增强代入感"

    - name: "Victim_POV"
      description: "被攻击者视角"
      use_case: "展示威胁感"
```

#### 连招序列设计

```yaml
Combo_Design:
  description: "多段连招的镜头编排"

  three_hit_combo:
    sequence:
      - "Wide - 双方对峙"
      - "Medium - A启动"
      - "Close - 第一击"
      - "Close - 第二击（更快）"
      - "Close - 第三击（最快）"
      - "Medium - B被击退"
      - "Close - B痛苦表情"
      - "Wide - A追击姿态"
    rhythm_pattern: "1-2-3，逐渐加速"

  counter_attack:
    sequence:
      - "Medium - A攻击（被格挡）"
      - "Close - B格挡特写"
      - "Medium - B反击"
      - "Close - A被击中"
      - "Wide - A倒地"
    rhythm_pattern: "攻击-停顿-反击"
```

### 2. 追逐镜头系统 (Chase_Sequence)

#### 追逐镜头语法

```yaml
Chase_Sequence:
  description: "追逐场景的镜头序列设计"
  core_principle: "保持方向一致性，营造速度感"

  shot_types:
    pursuer_shots:
      - name: "Pursuer_Front"
        description: "追逐者正面，展示决心"
        camera: "正面跟拍"

      - name: "Pursuer_Back"
        description: "追逐者背面，展示速度"
        camera: "后方跟拍"

    pursued_shots:
      - name: "Pursued_Front"
        description: "被追者正面，展示恐惧"
        camera: "前方倒拍"

      - name: "Pursued_Back"
        description: "被追者背面，展示逃跑"
        camera: "后方跟拍"

    relationship_shots:
      - name: "Distance_Shot"
        description: "展示双方距离"
        camera: "侧面长焦压缩"

      - name: "Over_Shoulder_Chase"
        description: "过肩拍，展示即将被追上"
        camera: "追逐者肩膀后方"

  speed_techniques:
    - name: "Motion_Blur"
      description: "运动模糊增强速度感"

    - name: "Rapid_Cutting"
      description: "快速剪辑点"
      duration_per_shot: "0.5-1s"

    - name: "Dutch_Angle"
      description: "倾斜构图增加不稳定感"

    - name: "Foreground_Elements"
      description: "前景物体快速掠过"
```

#### 追逐序列模板

```yaml
Chase_Templates:
  foot_chase:
    sequence:
      - "Wide - 追逐开始，建立方向"
      - "Pursued_Front - 恐惧表情"
      - "Pursuer_Back - 快速移动"
      - "Distance_Shot - 展示距离"
      - "Pursued_Back - 回头看"
      - "Close - 障碍物特写（跳过）"
      - "Pursuer_Front - 决心表情"
      - "Wide - 追逐继续"
    rhythm: "快-快-慢-快"

  car_chase:
    sequence:
      - "Wide - 两车位置"
      - "Interior_A - 驾驶员专注"
      - "Exterior_Side - 两车并行"
      - "Interior_B - 紧张表情"
      - "POV_Driving - 速度感"
      - "Wide - 危险动作"
      - "Reaction_Shot - 路人反应"
      - "Close - 碰撞瞬间"
```

### 3. 爆破镜头系统 (Explosion_Sequence)

#### 爆破时间轴

```yaml
Explosion_Sequence:
  description: "爆炸场景的分镜时间轴"

  timeline:
    pre_explosion:
      - shot: "Setup"
        duration: "2-5s"
        description: "建立场景，制造预期"
        tension_building: true

      - shot: "Trigger"
        duration: "0.5-1s"
        description: "引爆瞬间（按钮、倒计时归零等）"

    explosion:
      - shot: "Initial_Blast"
        duration: "0.2-0.5s"
        description: "爆炸初始闪光"
        effects: "过曝、白屏"

      - shot: "Fireball"
        duration: "0.5-1s"
        description: "火球扩散"
        camera: "广角，低角度"

      - shot: "Debris"
        duration: "1-2s"
        description: "碎片飞溅"
        technique: "慢动作或正常速度"

    post_explosion:
      - shot: "Shockwave"
        duration: "0.5-1s"
        description: "冲击波效果"

      - shot: "Aftermath_Wide"
        duration: "2-3s"
        description: "爆炸后全景"

      - shot: "Character_Reaction"
        duration: "1-2s"
        description: "人物被冲击波影响"

      - shot: "Smoke_Fire"
        duration: "2-4s"
        description: "烟雾和余火"

  camera_techniques:
    - "轻微震动模拟冲击"
    - "快速推拉增加冲击感"
    - "多角度快速剪辑"
```

### 4. 节奏控制引擎 (Rhythm_Engine)

#### 动态节奏调整

```yaml
Rhythm_Engine:
  description: "根据动作强度自动调整剪辑节奏"

  intensity_mapping:
    calm:
      shot_duration: "2-5s"
      transition_type: "标准剪辑"
      music_tempo: "慢"

    building:
      shot_duration: "1-2s"
      transition_type: "快速剪辑"
      music_tempo: "渐快"

    peak:
      shot_duration: "0.3-0.8s"
      transition_type: "极快剪辑"
      music_tempo: "快"

    release:
      shot_duration: "2-4s"
      transition_type: "慢动作或定格"
      music_tempo: "慢下来"

  breathing_points:
    - "每15-20秒需要一个停顿"
    - "大动作后需要恢复镜头"
    - "情绪转折处放慢节奏"
```

### 5. 空间定位系统 (Spatial_System)

#### 动作空间管理

```yaml
Spatial_System:
  description: "保持复杂动作场景的空间一致性"

  orientation_markers:
    - "固定参考物（柱子、墙壁等）"
    - "地面标记"
    - "背景特征"

  coverage_strategy:
    - "定期回到全景重新定位"
    - "使用匹配剪辑保持方向"
    - "避免180°翻转"

  group_fights:
    - "使用颜色/服装区分阵营"
    - "固定区域分配"
    - "主次分明，聚焦主要冲突"
```

## 使用示例

### 示例1：街头格斗

**场景**：狭窄巷道的1v1格斗
**风格**：写实、gritty

```
序列设计：
1.  [3s]   Wide   - 巷道全景，两人对峙
2.  [1s]   Medium - A摆出格斗姿态
3.  [0.5s] Close  - A眼神特写（决心）
4.  [0.5s] Close  - B冷笑
5.  [0.3s] Close  - A出拳
6.  [0.3s] Close  - 拳头击中B面部
7.  [0.8s] Medium - B踉跄后退
8.  [0.5s] Close  - B擦嘴角血迹
9.  [0.4s] Medium - B反击踢腿
10. [0.3s] Close  - A格挡
11. [0.3s] Close  - A抓住B的腿
12. [0.5s] Medium - A将B摔倒
13. [2s]   Wide   - B倒地，A站立
```

### 示例2：屋顶追逐

**场景**：城市屋顶跑酷追逐
**风格**：紧张、快速

```
序列设计：
1.  [2s]   Wide           - 屋顶全景，展示地形
2.  [1s]   Pursued_Front  - 逃跑者惊恐表情
3.  [0.8s] Pursuer_Back   - 追逐者快速移动
4.  [0.5s] Close          - 跨越障碍物的脚
5.  [0.8s] Distance_Shot  - 展示距离在缩短
6.  [0.5s] POV            - 追逐者视角看到逃跑者
7.  [0.5s] Close          - 逃跑者回头看
8.  [0.6s] Wide           - 危险跳跃
9.  [0.4s] Close          - 手抓住边缘
10. [1s]   Over_Shoulder  - 即将被抓住的紧张
11. [2s]   Wide           - 逃跑者成功跳到下一栋楼顶
```

### 示例3：汽车爆炸

**场景**：停车场汽车爆炸
**风格**：震撼、慢动作

```
序列设计：
1.  [4s]   Wide          - 停车场，主角走向汽车
2.  [2s]   Close         - 主角发现异常
3.  [1s]   Close         - 倒计时显示00:01
4.  [0.3s] Extreme_Close - 主角瞳孔收缩
5.  [0.2s] White_Screen  - 爆炸闪光
6.  [1s]   Slow_Mo       - 火球扩散
7.  [2s]   Slow_Mo       - 碎片飞溅
8.  [1s]   Normal        - 主角被冲击波掀飞
9.  [3s]   Wide          - 燃烧的汽车残骸
10. [2s]   Close         - 主角倒地，耳鸣效果
```

## 详细示例：巷战完整分镜

**场景设定**：
- 地点：狭窄的城市后巷
- 人物：主角（便衣警察）、反派（持刀歹徒）
- 风格：写实、gritty、紧张

**完整镜头序列**：

| 镜号 | 镜头类型 | 景别 | 时长 | 画面描述 | AI提示词要点 |
|-----|---------|------|-----|---------|-------------|
| 1 | Wide | 全景 | 3s | 狭窄巷道，两人对峙，垃圾散落 | narrow urban alley, two men facing off, gritty atmosphere, cinematic lighting |
| 2 | Medium | 中景 | 1s | 主角摆出格斗姿态，手摸向腰间 | plainclothes detective, combat stance, reaching for holster, tense |
| 3 | Close | 特写 | 0.5s | 主角眼神锐利，下定决心 | extreme close up, detective's determined eyes, intense gaze |
| 4 | Close | 特写 | 0.5s | 反派冷笑，露出刀锋 | villain smirking, knife glinting, menacing expression |
| 5 | Close | 特写 | 0.3s | 主角出拳，动作模糊 | punch in motion, motion blur, dynamic action |
| 6 | Close | 特写 | 0.3s | 拳头击中反派面部，冲击感 | impact shot, fist connecting, cinematic impact |
| 7 | Medium | 中景 | 0.8s | 反派踉跄后退，撞墙 | villain stumbling back, hitting wall, disoriented |
| 8 | Close | 特写 | 0.5s | 反派擦嘴角血迹，眼神变凶狠 | villain wiping blood, eyes turning vicious |
| 9 | Medium | 中景 | 0.4s | 反派反击踢腿 | villain kicking, aggressive movement |
| 10 | Close | 特写 | 0.3s | 主角双臂格挡 | protagonist blocking, defensive posture |
| 11 | Close | 特写 | 0.3s | 主角抓住反派脚踝 | hand grabbing ankle, grappling |
| 12 | Medium | 中景 | 0.5s | 主角将反派摔倒在地 | takedown move, dynamic action |
| 13 | Wide | 全景 | 2s | 反派倒地，主角站立俯视 | aftermath, dominant position, alley setting |

## 与现有Skill对接

### 对接导演分镜系统

```yaml
integration:
  action_scenes:
    input: "动作场景剧本描述"
    process: "Action_Sequence_Designer生成镜头序列"
    output: "分镜表（含时间码、镜头类型）"
```

### 对接镜头画面设计

- 动作场景需要特殊的动态构图考虑
- 镜头画面设计Skill负责：运动模糊参数、动态构图（预留动作空间）、特效镜头参数

### 对接竖屏短剧节奏优化

```yaml
vertical_adaptation:
  considerations:
    - "动作方向改为垂直（垂直方向的跳跃/下落更有冲击力）"
    - "增加特写比例（竖屏面部特写优势）"
    - "减少水平移动的全景"
    - "节奏更快（平均镜头时长减少30-40%）"
```

## 提示词模板

### 基础提示词

```
你是一个专业的动作片分镜师。请为以下场景设计镜头序列：

场景类型：[打斗/追逐/爆炸]
场景描述：
[详细描述]

风格要求：[写实/夸张/紧张/震撼]
参与人数：[人数]

请输出：
1. 完整镜头序列（含时长）
2. 每个镜头的AI绘画提示词
3. 节奏建议
```

### 高级提示词

```
作为好莱坞动作片分镜专家，请为以下场景设计专业镜头序列：

场景：
[详细描述]

参考风格：[如：《谍影重重》《疾速追杀》等]

技术要求：
- 剪辑节奏：[快速/中等/缓慢]
- 摄影风格：[手持/稳定器/轨道]
- 特效强度：[写实/夸张]

请提供：
1. 分镜表（镜号、镜头类型、时长、画面描述）
2. 空间示意图
3. 节奏曲线图
4. AI绘画提示词
```

## 参数速查表

| 场景类型 | 平均镜头时长 | 特写比例 | 节奏特点 |
|---------|-------------|---------|---------|
| 写实打斗 | 0.5-1.5s | 40% | 快速、断续 |
| 武侠打斗 | 1-3s | 30% | 流畅、连贯 |
| 追逐 | 0.8-2s | 35% | 持续紧张 |
| 爆炸 | 0.2-2s | 50% | 快慢结合 |

## 版本记录

- v1.0 (2024-02) - 初始版本，包含打斗、追逐、爆破三大系统