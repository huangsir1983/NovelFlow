# Latest TapNow Integration

更新时间：2026-03-29

## 目标

以 `TapNow / TapFlow` 式可执行无限画布为中枢，把当前项目资产库推进成 `Shot` 级生产入口，并把中段工作台稳定推进到：

`资产就绪 -> 模块化 Shot 工作流 -> 图像批准 -> Animatic 校验 -> 视频批准 -> Sequence Bundle`

这一阶段的终点不是最终成片，而是：

- `approved shot videos`
- `shot order`
- `transition hints`
- `audio/subtitle placeholders`
- `animatic references`

然后交给下一阶段预剪辑，并最终导出到剪映。

## 当前代码落点

### 页面壳层

- `packages/web/src/app/[locale]/projects/[id]/page.tsx`

这里保留原来的 stage tabs，但已经把：

- `assets` 接成 `ProductionAssetHub`
- `canvas` 接成 `ShotProductionBoard`
- `preview` 接成 `PreviewAnimaticWorkspace`

### 新增共享类型

- `packages/shared/src/types/production.ts`

冻结了本轮主链路的核心结构：

- `AssetAnchor`
- `ShotProductionSpec`
- `WorkflowModule`
- `AssetRequirement`
- `ShotRuntimeArtifact`
- `ShotNodeRun`
- `WritebackPreview`
- `AnimaticClipRef`
- `ShotVideoSequenceBundle`

### 新增共享推导逻辑

- `packages/shared/src/lib/production.ts`

承接：

- 从 `Project Truth Layer` 推导 `ShotProductionSpec[]`
- 默认模块库推荐
- 初始 node runs / writeback
- image/video artifact 候选生成
- animatic clips 聚合
- sequence bundle 聚合

### 新增共享组件

- `packages/shared/src/components/production/ProductionAssetHub.tsx`
- `packages/shared/src/components/production/ShotProductionBoard.tsx`
- `packages/shared/src/components/production/PreviewAnimaticWorkspace.tsx`

### Store 升级

- `packages/shared/src/stores/boardStore.ts`
- `packages/shared/src/stores/previewStore.ts`

现在不再只是旧版 `ShotCard + relations` 占位，而是承接：

- shot queue
- workflow modules
- node runs
- artifacts
- writebacks
- run console
- animatic clips
- sequence bundles
- clip duration override

## 这版的产品结构

### 1. Production Asset Hub

资产库顶部增加了：

- `Board Readiness`
- `Shot Queue`
- `Asset Requirement`
- `进入当前 Shot`
- `进入镜头生产`

底部仍然保留原有资产库编辑与图片锚定能力，避免丢掉旧能力。

### 2. Shot Production Board

不是空白画布，而是 Shot-first 的模板化执行台：

- 左侧：`Shot Queue`
- 中间：`Workflow Module Library + TapNow workflow chain + Animatic mini strip`
- 右侧：`Inspector + Asset Lock + Artifact Compare + Writeback Preview`
- 底部：`Run Console + Hard Gates`

硬门已经明确：

- 没有 `Image Approval` 不能进 `Animatic Checkpoint`
- 没过 `Animatic Checkpoint` 不能进 `Video Generation`
- 没有 `Video Approval` 不能完成 `Writeback + Bundle`

### 3. Preview / Animatic Workspace

不是旧版大桌面，而是轻量 Preview 工作台：

- `clip strip`
- `playhead`
- `heatmap / rhythm notes`
- `duration edit`
- `source jumpback`
- `sequence bundle detail`

## 数据流说明

### 资产库 -> 画布

页面层不再把原始资产对象整包塞进中段，而是先通过：

- `buildShotProductionProjection(...)`

把当前：

- scenes
- shots
- characters
- locations
- props
- assetImages
- assetImageKeys
- stylePreset

推导成：

- `ShotProductionSpec[]`
- `AssetRequirement[]`
- `BoardReadinessSummary`
- `WorkflowModule[]`

### 画布 -> Preview

页面层会持续把 Board 的执行态推导成：

- `AnimaticClipRef[]`
- `ShotVideoSequenceBundle`

并同步进 `previewStore`。

### Preview -> 回跳来源

任意 clip 都保留：

- `shotId`
- `sourceNodeId`
- `sourceModuleId`
- `artifactId`

所以 Preview 可以直接回跳到来源 Shot。

## 模块库

当前内置第一批模块：

- 建立镜头模块
- 对白镜头模块
- 打斗镜头模块
- 抒情镜头模块
- 转场镜头模块
- 情绪特写模块
- 跟拍动作模块

默认逻辑是：

- 模块优先
- Shot-first
- 结果优先
- 显式 writeback
- Animatic 作为硬门

## 旧版借鉴边界

这次只借旧版逻辑，不借旧版结构：

- 借：统一数据总线思路
- 借：AssetRequirement
- 借：Animatic 的 timeline / playhead / conflict judgement / jumpback
- 不借：大一统 giant canvas
- 不借：PyQt 图形实现
- 不借：把运行结果直接塞回 Scene 主对象

## 下一步建议

如果继续深化，建议按这个顺序：

1. 把当前前端内存态替换成真实 API：`shot-production-specs / instantiate-module / animatic/build / sequence-bundles`
2. 给 `Workflow Module` 增加保存、克隆、团队共享与版本化
3. 把当前 Board 中间区从步骤卡升级成真正的可执行节点画布
4. 把 Preview 的 clip duration / transition edit 反写进真实 preview document
5. 增加 100+ Shot 项目的性能优化与虚拟列表
