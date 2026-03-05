# 镜头序列Skill合集

## 概述
本Skill合集提供AI视频创作中**镜头序列设计**的完整解决方案，涵盖五大核心场景类型。

- **作者**: （AI替代人类公众号）
- **版本**: v1.0
- **适用领域**: AI视频分镜设计

## 文件清单

| 文件名 | Skill名称 | 核心内容 |
|-------|-----------|---------|
| `Dialogue_Shot_Sequence_Designer.md` | 对话场景镜头序列设计 | 正反打、过肩镜头、反应链 |
| `Action_Sequence_Designer.md` | 动作戏镜头序列设计 | 打斗、追逐、爆破的节奏控制 |
| `Emotional_Sequence_Designer.md` | 情感戏镜头序列设计 | 爱情、悲伤、冲突的细腻渲染 |
| `Suspense_Thriller_Designer.md` | 悬疑惊悚镜头序列设计 | 紧张感、反转、Jump Scare |
| `Montage_Transition_Designer.md` | 蒙太奇与转场序列设计 | 时间压缩、平行叙事、匹配剪辑 |

## Skill关系图

```
导演分镜系统（上游）
    │
    ├── Dialogue_Shot_Sequence_Designer（对话场景）
    ├── Action_Sequence_Designer（动作场景）
    ├── Emotional_Sequence_Designer（情感场景）
    ├── Suspense_Thriller_Designer（悬疑场景）
    └── Montage_Transition_Designer（蒙太奇与转场 —— 连接所有场景Skill）
            │
            ▼
    镜头画面设计Skill（下游：细化每个镜头的视觉参数）
    竖屏短剧节奏优化Skill（下游：横竖屏适配）
```

## 使用流程

1. **剧本分析**：使用"导演分镜系统"拆解剧本，标记场景类型
2. **场景分镜**：根据场景类型调用对应Skill生成镜头序列
3. **场景连接**：使用"蒙太奇与转场Skill"设计场景之间的过渡
4. **画面细化**：使用"镜头画面设计Skill"为每个镜头生成详细视觉参数与AI绘画提示词
5. **格式适配**：如需竖屏，使用"竖屏短剧节奏优化Skill"进行适配

## 版本记录

- v1.0 (2024-02) - 初始版本，包含五大场景Skill