# 无限画布 - 小说到视频制作系统

## 项目结构

```
infinite-canvas/
├── src/
│   ├── types/
│   │   ├── index.ts              # 所有核心类型定义
│   │   └── api.ts                # API请求/响应类型
│   ├── store/
│   │   ├── canvasStore.ts        # 画布状态 (Zustand)
│   │   ├── projectStore.ts       # 项目/资产状态
│   │   └── agentStore.ts         # Agent任务队列状态
│   ├── components/
│   │   ├── Canvas/
│   │   │   ├── InfiniteCanvas.tsx      # 主画布容器
│   │   │   ├── CanvasRenderer.tsx      # 虚拟化渲染器
│   │   │   ├── ConnectionLayer.tsx     # SVG连线层
│   │   │   ├── MiniMap.tsx             # 小地图
│   │   │   └── Toolbar.tsx             # 工具栏
│   │   ├── Nodes/
│   │   │   ├── BaseNode.tsx            # 节点基类
│   │   │   ├── StoryboardNode.tsx      # 分镜文本节点
│   │   │   ├── ImageNode.tsx           # 图片合成节点
│   │   │   ├── VideoNode.tsx           # 视频生成节点
│   │   │   └── NodeInspector.tsx       # 节点属性面板
│   │   ├── Modules/
│   │   │   ├── ModuleBlock.tsx         # 模块区域块
│   │   │   ├── ModuleTemplates.ts      # 5类模块定义
│   │   │   └── ModulePanel.tsx         # 左侧模块面板
│   │   └── Panels/
│   │       ├── AssetPanel.tsx          # 资产库面板
│   │       └── ChainProgressPanel.tsx  # 分镜链进度面板
│   ├── services/
│   │   ├── claudeAgent.ts        # Claude API Agent服务
│   │   ├── imageService.ts       # 图片合成工作流
│   │   ├── videoService.ts       # 视频生成（即梦/可灵）
│   │   └── workflowEngine.ts     # 工作流执行引擎
│   ├── hooks/
│   │   ├── useCanvas.ts          # 画布交互Hook
│   │   ├── useLazyNodes.ts       # 懒加载Hook
│   │   └── useWorkflow.ts        # 工作流Hook
│   └── utils/
│       ├── geometry.ts           # 坐标计算工具
│       ├── layout.ts             # 自动布局算法
│       └── chainAnalyzer.ts      # 分镜链分析器
├── public/
└── package.json
```

## 技术栈
- React 18 + TypeScript
- Zustand (状态管理)
- React Query (服务器状态)
- Framer Motion (动画)
- Anthropic SDK (Claude opus-4-6)
- Tailwind CSS

## 接入说明
见 CLAUDE_CODE_PROMPT.md
