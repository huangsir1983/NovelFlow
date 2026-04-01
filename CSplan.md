# CSplan（两周MVP冲刺版）

> 目标：在**不改变现有业务流程顺序**（小说导入→分析→场景/资产→分镜→图像/视频→成片导出）的前提下，2周内完成可上线MVP，并具备100+在线、任务峰值100+（极限200）下的可运行能力。

---

## 0. 项目边界与约束

### 0.1 本次MVP必须交付（全部必须）
- 小说导入 + 分析 + 场景提取
- 分镜 / 镜头组
- 图像生成
- 视频生成（单镜头）
- 项目级成片导出（MVP版）
  - 按镜头顺序拼接
  - 基础转场
  - 背景音
  - 字幕草稿
  - 可编辑时间线

### 0.2 并发目标（统一口径）
- 日常在线：100+
- 高峰瞬时提交任务：100+（极限200）
- 队列同时运行任务：100+（极限200）

### 0.3 SLA目标
- 页面API：P95 < 500ms
- 新建导入任务排队：< 30s
- 管道成功率：> 95%

### 0.4 部署与预算
- 平台：阿里云 ACK/K8s
- 队列：Celery + Redis
- 前期预算：约 ¥10,000 / 月（后期按项目扩展）

### 0.5 合规与审计（必须）
每个任务必须记录：
- user_id
- project_id
- task_id
- model
- input_digest（输入摘要/哈希）
- output_asset_urls
- elapsed_ms
- estimated_cost
- status

### 0.6 数据保留策略
- 原小说文本：7~14天
- 生成图/视频：7~14天（或按项目配置）
- 日志与审计：7~14天（建议审计可延长至30天）

---

## 1. 里程碑总览（每3~4天）

### M1（Day1~Day3）：P0基础解耦
- ImportPipeline剥离到Celery Worker
- API职责收敛为：入队/查状态/取消
- 回滚预案验证（checkpoint + git）

### M2（Day4~Day7）：P0上线底座
- 生产固定PostgreSQL（禁SQLite生产路径）
- OSS接入（文件与中间产物不落本地）
- SSE网关参数定型与重连策略稳定

### M3（Day8~Day10）：P1稳定性增强
- 分级队列（导入/图像/视频）
- 三级限流（全局/租户/项目）与429降级链路
- 关键索引与慢查询治理

### M4（Day11~Day14）：P2最小商业能力 + 发布
- 成本中心（项目级token/image/video）
- 四级配额并发策略
- 灰度发布 + 回滚机制
- 压测、验收、上线清单

---

## 2. 分阶段实施清单（不改主流程）

## P0（上线前必须）

### P0-1 ImportPipeline剥离到任务队列
**目标**：API无重活，Worker专职跑管道。

**改造点**：
1. 新建 `backend/tasks/celery_app.py`
2. 新建 `backend/tasks/import_tasks.py`，封装 `ImportPipeline.run()`
3. `backend/api/import_novel.py`
   - `_submit_pipeline*` 改为 `celery_app.send_task(...)`
   - 状态查询统一走DB
   - 取消改为“写取消标志 + worker轮询退出”
4. 将线程池仅保留为开发兼容（可选）

**完成标准**：
- API pod重启不导致运行中任务全部丢失
- 同时100+任务入队可稳定排队
- 任务状态可追踪（pending/running/failed/completed/cancelled）

---

### P0-2 生产固定PostgreSQL
**目标**：生产环境彻底去SQLite分支。

**改造点**：
1. `config.py` 增加生产校验：`DATABASE_URL` 必须为 postgres
2. `database.py` 中生产禁用SQLite特定逻辑
3. `monitor.py` 标注 dev-only，不进入生产镜像
4. 增加迁移脚本与启动检查（Alembic/启动时校验）

**完成标准**：
- 生产环境启动若非Postgres立即失败并报警
- 数据库连接池稳定，无SQLite锁错误

---

### P0-3 OSS对象存储接入
**目标**：输入/中间/输出资产全部对象存储化。

**改造点**：
1. 新建 `services/storage_adapter.py`
   - LocalStorage（dev）
   - OSSStorage（prod）
2. 导入文件、生成图片、生成视频、导出成片均写OSS
3. DB仅保存 key/url/meta，不保存大二进制

**完成标准**：
- 本地磁盘无关键产物依赖
- Worker可无状态扩容

---

### P0-4 SSE网关参数定型
**目标**：高并发长连接稳定。

**ACK/Nginx建议**：
- `proxy_read_timeout=3600s`
- `proxy_send_timeout=3600s`
- `keepalive_timeout=75s`
- 每15s heartbeat
- 前端重连：指数退避 2/4/8/16/30s

**完成标准**：
- 30分钟长任务SSE不断流
- 断网重连后可继续感知任务状态

---

## P1（几百在线稳定运行）

### P1-1 分级队列
**目标**：互不干扰，避免长任务阻塞短任务。

队列规划：
- `queue_import`
- `queue_image`
- `queue_video`
- `queue_export`（成片导出）

并发建议（初版）：
- import worker concurrency: 24
- image worker concurrency: 48
- video worker concurrency: 16
- export worker concurrency: 12

---

### P1-2 AI限流治理（三级）
**目标**：高峰不雪崩。

- 全局限流：平台总RPM/TPM
- 租户限流：每租户最大并发任务
- 项目限流：单项目最大并发任务
- 429策略：自动退避 + 模型降级（advanced→standard→fast）

---

### P1-3 索引与慢查询治理
必须索引：
- `import_tasks(project_id, created_at DESC)`
- `scenes(project_id, "order")`
- `shot_groups(project_id, scene_id, "order")`

建议补充：
- `ai_call_logs(project_id, created_at DESC)`
- `characters(project_id, name)`

**完成标准**：
- 关键列表API P95 < 500ms
- 无明显全表扫描热点

---

## P2（商业化最小能力）

### P2-1 成本中心
- 按项目聚合 token/image/video 成本
- 日报/项目账单视图
- 超预算告警与自动降级

### P2-2 四级分层与并发上限（按并发任务数）
> 可后续按真实成本微调

- **Level1（体验）**：并发 1，总排队上限 5
- **Level2（标准）**：并发 3，总排队上限 20
- **Level3（专业）**：并发 8，总排队上限 80
- **Level4（企业）**：并发 20，总排队上限 200

### P2-3 灰度发布与回滚
- 任务记录 `pipeline_version`
- 灰度比例：5% → 20% → 50% → 100%
- 任一阶段失败率超阈值自动回滚到上版本

---

## 3. 阿里云落地配置单（100/300/500档）

> 以下为启动建议，最终以压测结果回填。

## 档位A：100在线（目标100+，极限200峰值提交）
- ACK：
  - API Deployment：3副本（2C4G）
  - Worker Import：3副本（4C8G）
  - Worker Image：2副本（4C8G）
  - Worker Video：2副本（8C16G）
  - Worker Export：1副本（4C8G）
- PostgreSQL（RDS）：4C8G（高可用）
- Redis（主从）：4C8G
- OSS：标准存储 + 生命周期（14天）

## 档位B：300在线
- API：6副本（4C8G）
- Import：6副本（8C16G）
- Image：4副本（8C16G）
- Video：4副本（16C32G）
- Export：2副本（8C16G）
- PostgreSQL：8C32G + 只读实例
- Redis：8C16G（建议集群）

## 档位C：500在线
- API：10副本（4C8G）
- Import：10副本（16C32G）
- Image：8副本（16C32G）
- Video：6副本（16C32G）
- Export：4副本（16C32G）
- PostgreSQL：16C64G（高可用+读写分离）
- Redis：16C32G（集群）

---

## 4. 容量与预算上限（初版）

## 4.1 并发预算闸门（必须）
- 全局同时运行任务上限：120（硬阈值）
- 软阈值（告警）：90
- 入队超过阈值自动排队，严格禁止硬抢占

## 4.2 月预算（前期¥10,000）分配建议
- 计算资源（ACK+RDS+Redis+网关）：40%
- 对象存储与带宽：15%
- AI调用成本池：40%
- 监控日志：5%

## 4.3 成本熔断规则
- 日成本达到预算的70%：降级到standard模型优先
- 达到90%：限制Level1/2新重任务
- 达到100%：仅保留白名单与关键任务

---

## 5. 测试计划（每阶段必须过）

## 5.1 功能测试
- 小说导入→分析→场景→分镜→图像→视频→导出 全链路回归
- 任务取消/重试/恢复
- SSE断连重连一致性

## 5.2 性能测试
- API压测：P95/P99、错误率
- 队列压测：100/150/200并发任务提交
- 数据库压测：关键SQL慢查询与锁等待

## 5.3 稳定性测试
- Chaos：杀worker、重启API、Redis短暂不可用
- 验证任务最终一致性与可恢复性

## 5.4 验收门槛
- API P95 < 500ms
- 队列新任务排队 < 30s（目标档位）
- 管道成功率 > 95%

---

## 6. 故障修复闭环（SRE流程）

1. **发现**：告警触发（失败率/排队时长/API延迟）
2. **止损**：限流、降级模型、暂停低优先级队列
3. **定位**：按 task_id / trace_id / project_id 追踪
4. **修复**：热修复或回滚（pipeline_version）
5. **回归**：核心链路自动化回归 + 小流量复验
6. **复盘**：记录根因、影响范围、修复时长、预防项

---

## 7. Day1~Day14 每日执行看板模板（必须）

> 每天早晚各更新一次。可直接复制到飞书/Notion/Jira。

### DayX 模板
- 今日目标：
- 负责人：
- 预计工时：
- 实际完成：
- 风险与阻塞：
- 决策记录：
- 回滚点：
  - Git: `commit hash / tag`
  - Cursor Checkpoint: `name`
- 验证结果：
  - 功能：
  - 性能：
  - 稳定性：
- 次日计划：

---

## 8. 两周每日任务建议（可直接执行）

### Day1
- 建立基线：checkpoint + `git commit -m "before-video-pipeline"`
- 新建Celery app骨架、worker启动脚本

### Day2
- import_novel入队改造（仅改执行层，不改业务逻辑）
- 任务状态回写DB

### Day3
- 取消/重试/恢复链路打通
- M1验收

### Day4
- 生产Postgres强校验
- 移除生产SQLite路径

### Day5
- OSS storage adapter接入上传与中间文件

### Day6
- 生成图/视频产物写OSS
- 导出素材元数据回写

### Day7
- SSE网关参数定型 + 前端重连策略验证
- M2验收

### Day8
- 分级队列：import/image/video/export
- worker并发参数初调

### Day9
- 三级限流策略落地（全局/租户/项目）
- 429退避与降级链路

### Day10
- 索引上线 + 慢查询分析 + SQL优化
- M3验收

### Day11
- 成本中心最小实现（项目账本）

### Day12
- 四级并发配额落地（Level1~4）

### Day13
- 灰度发布/回滚流程演练
- 压测100+/极限200场景

### Day14
- 全链路验收、发布清单、上线窗口
- M4验收

---

## 9. 发布与回滚策略

### 发布前检查（必须全绿）
- 数据库迁移成功
- worker健康检查正常
- 队列堆积在阈值内
- SLA压测达标

### 快速回滚
- 应用版本回滚：Helm rollback
- pipeline版本回滚：切回上一个 `pipeline_version`
- 数据回滚：仅做前向修复，避免破坏任务审计链

---

## 10. 结论

在不改变现有业务流程的前提下，本计划可在2周内达成“可用MVP + 可扩展底座”。
真正支撑100+在线与峰值100~200任务，关键不在业务逻辑重写，而在：
- 执行层队列化
- 存储对象化
- 生产数据库规范化
- 限流与可观测治理

以上四点必须优先完成（P0 + P1核心项）。
