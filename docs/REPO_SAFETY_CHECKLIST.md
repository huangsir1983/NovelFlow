# 仓库安全清单

> 项目：虚幻造物 `NovelFlow-main`
> 日期：2026-03-06
> 目的：避免误删正式源码、正式文档、知识资产与配置文件；统一“哪些绝对不能删、哪些可以安全清理、哪些需要先确认”的操作边界。

---

## 1. 使用原则

本清单用于回答三个问题：

1. 哪些是核心文件，不能误删
2. 哪些是可删缓存或临时产物，可以放心清理
3. 哪些目录风险极高，必须列为禁止误删目录

执行删除前，默认遵循以下规则：

- 不做整仓库模糊删除
- 不执行无范围限制的递归删除
- 不删除未确认用途的目录
- 先查引用，再删除
- 优先删除明确命名的缓存、日志、临时文件
- 对不确定文件，先移动到人工回收区，再延迟删除

---

## 2. 核心文件

以下文件属于项目核心文件，默认禁止删除：

### 2.1 根目录核心文档与配置

- `PRD.md`
- `newplan1.md`
- `newplan2.md`
- `FINAL_ROADMAP.md`
- `list.md`
- `CLAUDE.md`
- `package.json`
- `pnpm-lock.yaml`
- `pnpm-workspace.yaml`
- `turbo.json`
- `.gitignore`
- `.gitattributes`

### 2.2 关键目录

- `backend/`
- `packages/`
- `docs/`
- `scripts/`
- `知识库/`
- `界面设计规范/`

### 2.3 后端关键文件

以下文件直接影响后端运行与数据结构，不应误删：

- `backend/main.py`
- `backend/config.py`
- `backend/database.py`
- `backend/requirements.txt`
- `backend/api/`
- `backend/models/`
- `backend/services/`
- `backend/agents/`
- `backend/knowledge/`

### 2.4 前端关键目录

- `packages/shared/`
- `packages/web/`

### 2.5 正式设计与规划文档

以下文档已形成当前正式口径，默认禁止删除：

- `docs/TRI_STAGE_CREATIVE_UX.md`
- `docs/MIDDLE_STAGE_WORKBENCH_DECISION_REPORT.md`
- `docs/CANVAS_SYSTEM_DESIGN.md`
- `docs/CANVAS_COMPLEXITY_AND_FLOW.md`
- `docs/CANVAS_NODE_SPEC.md`
- `docs/CANVAS_PHASE1_TASKS.md`
- `docs/WORKFLOW_SCHEMA.md`
- `docs/CANVAS_API_SPEC.md`
- `docs/DECISION_LOG.md`
- `docs/PRD.md`
- `docs/newplan.md`
- `docs/plan.md`

---

## 3. 禁止误删目录

以下目录应视为“高风险目录”，默认禁止整目录删除：

### 3.1 绝对禁止直接删除

- `backend/`
- `packages/`
- `docs/`
- `知识库/`
- `界面设计规范/`

### 3.2 非必要不要整体删除

- `backend/api/`
- `backend/models/`
- `backend/services/`
- `backend/agents/`
- `backend/knowledge/`
- `packages/shared/`
- `packages/web/`

### 3.3 需要谨慎处理的隐藏目录

- `.claude/`

说明：`.claude/` 一般不是业务源码，但可能包含本地工具设置。可按团队习惯决定是否保留；默认不要自动删除整个目录。

---

## 4. 可删缓存

以下内容通常是可再生文件，可在需要清理环境时删除：

### 4.1 Node / Web 缓存

- `node_modules/`
- `.pnpm-store/`
- `.turbo/`
- `.next/`
- `dist/`
- `build/`
- `out/`
- `coverage/`
- `.cache/`
- `*.tsbuildinfo`

### 4.2 Python 缓存

- `__pycache__/`
- `*.pyc`
- `*.pyo`
- `*.pyd`
- `*.egg-info/`
- `.eggs/`

### 4.3 本地虚拟环境

- `venv/`
- `.venv/`
- `env/`

说明：删除虚拟环境不会删业务代码，但删除后需要重新安装依赖。

### 4.4 常见日志文件

- `*.log`
- `npm-debug.log*`
- `pnpm-debug.log*`

### 4.5 操作系统垃圾文件

- `.DS_Store`
- `Thumbs.db`
- `Desktop.ini`

---

## 5. 可删临时产物

以下类型通常不是正式产物，确认无引用后可删除：

### 5.1 编号分析文件

- `__*_numbered.txt`

### 5.2 调试脚本或一次性测试文件

- `__*.py`
- `__*.txt`
- 明显用于调试的 `stdout`、`stderr` 文本文件

### 5.3 补丁与失败残留

- `*.rej`
- `*.orig`
- `*.bak`
- `*.old`
- `*.tmp`
- `*.temp`

说明：这类文件通常先检查一次是否被文档引用；如无引用，可删除。

---

## 6. 需要先确认再处理的文件

以下对象不应自动删除，必须先确认：

- `.env`
- `.env.local`
- `.env.*.local`
- `*.db`
- `*.sqlite`
- `*.sqlite3`
- 未在文档中说明用途的单独 `.txt`、`.json`、`.md` 文件
- 新出现但不符合命名习惯的目录

原因：这些文件可能是本地配置、测试数据库、导出样本、外部交付件或中间成果。

---

## 7. 安全删除流程

建议以后统一按这个顺序操作：

### 7.1 第一步：确认目标类别

先判断目标属于：

- 核心文件
- 禁止误删目录
- 可删缓存
- 可删临时产物
- 待确认对象

### 7.2 第二步：查引用

如果不是明显缓存，先在仓库中搜索是否有引用：

- 文档引用
- 代码引用
- 配置引用
- 脚本引用

### 7.3 第三步：优先移动，不直接硬删

对不完全确定但大概率可删的对象，优先移动到临时回收目录，例如：

- `_trash/`
- `_quarantine/`

观察 1 到 3 天无影响，再彻底删除。

### 7.4 第四步：只做定点删除

只删除明确文件名或明确缓存目录，不做以下操作：

- 在仓库根目录执行无筛选递归删除
- 对 `docs/`、`backend/`、`packages/` 做整目录删除
- 删除 `知识库/`、`界面设计规范/`

---

## 8. 推荐命令策略

### 8.1 推荐

- 先列出候选文件
- 先搜索引用
- 再做定点删除

### 8.2 不推荐

- `rm -rf` 指向仓库根目录附近
- 模糊通配符覆盖正式目录
- 删除整个上层目录来“顺手清理”

---

## 9. 当前仓库的删除安全结论

基于当前仓库结构，以下判断成立：

### 9.1 可以安全清理的典型对象

- `node_modules/`
- `.next/`
- `.turbo/`
- `__pycache__/`
- `*.log`
- `__*_numbered.txt`
- 明显的一次性调试文件

### 9.2 不应自动清理的对象

- 所有 `.md` 正式文档
- `backend/` 下源码和配置
- `packages/` 下前端与共享源码
- `知识库/`
- `界面设计规范/`

---

## 10. 团队执行建议

建议团队以后固定采用以下约束：

- 删除前先读本清单
- 默认把 `docs/`、`backend/`、`packages/`、`知识库/` 视为禁删区
- 对临时文件统一使用前缀命名，例如 `__temp_`、`__debug_`
- 对不确定文件统一进入 `_quarantine/`，不要直接物理删除
- 在做大规模清理前，先导出一次文件列表快照

---

## 11. 最简判断规则

如果来不及完整判断，就按这条最简规则执行：

- 看到 `PRD`、`plan`、`roadmap`、`docs`、`backend`、`packages`、`知识库`、`界面设计规范`，一律不要删
- 看到 `node_modules`、`.next`、`.turbo`、`__pycache__`、`*.log`、`__*_numbered.txt`，通常可以删
- 看不懂用途的文件，不删，先问
