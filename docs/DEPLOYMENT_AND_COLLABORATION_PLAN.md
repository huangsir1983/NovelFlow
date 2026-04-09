# UnrealMake 公网部署与多人协作技术方案

> 文档版本: v1.0 | 日期: 2026-04-03
> 状态: 待实施 | 随时可执行

---

## 目录

1. [方案概述](#1-方案概述)
2. [基础设施选型](#2-基础设施选型)
3. [服务器部署方案](#3-服务器部署方案)
4. [用户认证系统](#4-用户认证系统)
5. [多人实时协作](#5-多人实时协作)
6. [权限与项目共享](#6-权限与项目共享)
7. [数据同步与冲突解决](#7-数据同步与冲突解决)
8. [分阶段实施路线](#8-分阶段实施路线)
9. [安全方案](#9-安全方案)
10. [成本估算](#10-成本估算)
11. [附录：配置模板](#附录配置模板)

---

## 1. 方案概述

### 目标

将 UnrealMake 从本地单机开发模式升级为公网可访问的多人协作平台，支持：

- 任意用户通过浏览器访问，不依赖本地电脑运行
- 多人同时操作同一个项目
- 项目级权限控制（所有者、编辑者、查看者）
- 数据持久化与安全

### 当前状态

| 组件 | 现状 | 目标 |
|------|------|------|
| 前端 | Next.js 15 + Turbopack，本地运行 | 部署到 Vercel / 云服务器 |
| 后端 | FastAPI，SQLite 单文件数据库 | Docker 部署，PostgreSQL |
| 存储 | 本地 `./uploads` 目录 | 阿里云 OSS |
| 队列 | 内存队列 | Redis + Celery |
| 认证 | 无 | JWT + OAuth |
| 协作 | 骨架 API（内存存储） | WebSocket 实时同步 |

---

## 2. 基础设施选型

### 推荐方案：阿里云 (国内用户优先)

| 服务 | 规格 | 月费参考 |
|------|------|----------|
| ECS 云服务器 | 2核4G (入门) / 4核8G (推荐) | ¥100-300 |
| RDS PostgreSQL | 1核2G 基础版 | ¥80-150 |
| Redis | 1G 标准版 | ¥50 |
| OSS 对象存储 | 按量计费 | ¥10-50 |
| 域名 + SSL | Let's Encrypt 免费证书 | ¥50/年 (域名) |
| CDN (可选) | 按量计费 | ¥10-30 |

### 替代方案

| 方案 | 适用场景 | 说明 |
|------|----------|------|
| 腾讯云 | 国内用户 | 与阿里云类似，选择优惠更大的 |
| AWS / GCP | 海外用户 | EC2/Cloud Run + RDS + S3 |
| Railway / Render | 快速原型 | 一键部署，但成本较高 |
| Vercel (前端) + 云服务器 (后端) | 混合部署 | 前端零运维，后端自控 |

### 推荐混合架构

```
用户浏览器
    │
    ├─── Vercel / Nginx ──── Next.js 前端 (SSR/SSG)
    │
    └─── API 网关 ──── 阿里云 ECS ──── FastAPI 后端
                            │
                            ├── PostgreSQL (RDS)
                            ├── Redis
                            └── OSS (文件存储)
```

---

## 3. 服务器部署方案

### 3.1 后端 Docker 化

**需要创建的文件: `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg2-binary gunicorn

# 应用代码
COPY . .

# 上传目录
RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["gunicorn", "main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "300"]
```

### 3.2 前端部署

**方案 A: Vercel (推荐，零运维)**

```bash
# 一键部署
cd packages/web
vercel deploy --prod
# 设置环境变量
# NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

**方案 B: Docker + Nginx**

```dockerfile
# packages/web/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY ../../package.json ../../pnpm-lock.yaml ../../pnpm-workspace.yaml ./
COPY packages/shared ./packages/shared
COPY packages/web ./packages/web
RUN corepack enable && pnpm install --frozen-lockfile
RUN pnpm build --filter=@unrealmake/web

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/packages/web/.next/standalone ./
COPY --from=builder /app/packages/web/.next/static ./.next/static
COPY --from=builder /app/packages/web/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### 3.3 完整 docker-compose.production.yml

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER:-unrealmake}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME:-unrealmake}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U unrealmake"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: always

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: always

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env.production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads:/app/uploads
    restart: always

  # 如果前端也用 Docker 部署（不用 Vercel 的情况）
  # frontend:
  #   build:
  #     context: .
  #     dockerfile: packages/web/Dockerfile
  #   ports:
  #     - "3000:3000"
  #   environment:
  #     NEXT_PUBLIC_API_URL: https://api.your-domain.com
  #   restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - backend
    restart: always

volumes:
  pgdata:
  redisdata:
  uploads:
```

### 3.4 Nginx 反向代理配置

```nginx
# nginx.conf
events { worker_connections 1024; }

http {
    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name api.your-domain.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name api.your-domain.com;

        ssl_certificate     /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        client_max_body_size 50M;

        location / {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket 支持（协作功能需要）
        location /ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 86400;
        }

        # SSE 支持
        location /api/projects/ {
            proxy_pass http://backend;
            proxy_set_header Connection '';
            proxy_http_version 1.1;
            proxy_buffering off;
            proxy_cache off;
            chunked_transfer_encoding off;
        }
    }
}
```

### 3.5 一键部署脚本

```bash
#!/bin/bash
# deploy.sh — 在服务器上执行

set -e

echo "=== UnrealMake 生产部署 ==="

# 1. 拉取最新代码
git pull origin main

# 2. 构建并启动
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

# 3. 等待数据库就绪
echo "等待服务启动..."
sleep 10

# 4. 健康检查
curl -sf http://localhost:8000/docs > /dev/null && echo "后端: OK" || echo "后端: FAIL"

echo "=== 部署完成 ==="
```

---

## 4. 用户认证系统

### 4.1 技术选型

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **JWT + 自建** | 完全可控，轻量 | 需自建登录/注册 | 推荐（MVP） |
| NextAuth.js + OAuth | 开箱即用，支持第三方登录 | 前后端耦合 | 适合中期 |
| Supabase Auth | 全托管，带 RLS | 引入外部依赖 | 适合快速上线 |
| Clerk / Auth0 | 企业级，UI 组件齐全 | 收费 | 适合团队协作场景 |

### 4.2 JWT 自建方案（推荐 MVP 起步）

#### 后端改动

**新增文件: `backend/api/auth.py`**

```python
# 核心端点
POST /api/auth/register     # 注册
POST /api/auth/login        # 登录，返回 JWT
POST /api/auth/refresh      # 刷新 token
GET  /api/auth/me           # 获取当前用户信息
POST /api/auth/logout       # 登出（黑名单 token）
```

**新增数据库模型: `backend/models/user.py`**

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    role = Column(String, default="user")  # user / admin
    created_at = Column(DateTime, default=func.now())
    
    # 关联
    projects = relationship("Project", back_populates="owner")
```

**认证中间件: `backend/middleware/auth.py`**

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token = Depends(security)):
    """验证 JWT token，返回当前用户"""
    payload = decode_jwt(token.credentials)
    user = db.query(User).get(payload["sub"])
    if not user:
        raise HTTPException(401, "Invalid token")
    return user
```

#### 前端改动

- 登录/注册页面组件
- `fetchAPI` 自动附带 `Authorization: Bearer <token>` 请求头
- token 存储在 `httpOnly cookie` (安全) 或 `localStorage` (简单)
- 路由守卫：未登录跳转登录页

#### 依赖

```
# backend/requirements.txt 新增
python-jose[cryptography]>=3.3.0  # JWT
passlib[bcrypt]>=1.7.4            # 密码哈希
```

### 4.3 第三方登录（中期扩展）

支持微信/GitHub/Google 登录：

```
POST /api/auth/oauth/wechat/callback
POST /api/auth/oauth/github/callback
POST /api/auth/oauth/google/callback
```

---

## 5. 多人实时协作

### 5.1 架构设计

```
浏览器 A ──┐                          ┌── 浏览器 B
           │    WebSocket 连接         │
           ├──── Nginx ──── FastAPI ────┤
           │         │                  │
浏览器 C ──┘         │                  └── 浏览器 D
                     │
              Redis Pub/Sub
           (多实例消息广播)
```

### 5.2 WebSocket 通道

**新增端点: `ws://api.domain.com/ws/projects/{project_id}`**

```python
# backend/api/ws.py

from fastapi import WebSocket, WebSocketDisconnect

class ConnectionManager:
    """管理 WebSocket 连接"""
    
    def __init__(self):
        # project_id -> set of connections
        self.rooms: dict[str, set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, project_id: str, user_id: str):
        await websocket.accept()
        self.rooms.setdefault(project_id, set()).add(websocket)
        # 广播「用户上线」
        await self.broadcast(project_id, {
            "type": "user_joined",
            "user_id": user_id,
            "timestamp": now()
        }, exclude=websocket)
    
    async def broadcast(self, project_id: str, message: dict, exclude=None):
        for conn in self.rooms.get(project_id, []):
            if conn != exclude:
                await conn.send_json(message)

manager = ConnectionManager()

@router.websocket("/ws/projects/{project_id}")
async def ws_project(websocket: WebSocket, project_id: str):
    user = await authenticate_ws(websocket)  # 从 query param 或 header 获取 token
    await manager.connect(websocket, project_id, user.id)
    try:
        while True:
            data = await websocket.receive_json()
            await handle_ws_message(project_id, user, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
```

### 5.3 消息类型

```typescript
// 前端 WebSocket 消息协议
type WSMessage =
  | { type: "user_joined"; user_id: string; username: string }
  | { type: "user_left"; user_id: string }
  | { type: "cursor_move"; user_id: string; position: { x: number; y: number } }
  | { type: "scene_updated"; scene_id: string; changes: Partial<Scene> }
  | { type: "beat_updated"; beat_id: string; changes: Partial<Beat> }
  | { type: "comment_added"; comment: Comment }
  | { type: "lock_acquired"; resource_type: string; resource_id: string; user_id: string }
  | { type: "lock_released"; resource_type: string; resource_id: string }
  | { type: "project_synced"; timestamp: string }
```

### 5.4 在线状态与光标

```typescript
// 前端 hook: useCollaboration
function useCollaboration(projectId: string) {
  const [onlineUsers, setOnlineUsers] = useState<CollabUser[]>([]);
  const [cursors, setCursors] = useState<Map<string, CursorPosition>>();
  
  useEffect(() => {
    const ws = new WebSocket(`wss://api.domain.com/ws/projects/${projectId}?token=${token}`);
    
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      switch (msg.type) {
        case "user_joined":
          setOnlineUsers(prev => [...prev, msg]);
          break;
        case "cursor_move":
          setCursors(prev => new Map(prev).set(msg.user_id, msg.position));
          break;
        // ...
      }
    };
    
    // 定期发送自己的光标位置
    const interval = setInterval(() => {
      ws.send(JSON.stringify({ type: "cursor_move", position: getCurrentCursorPos() }));
    }, 100);
    
    return () => { ws.close(); clearInterval(interval); };
  }, [projectId]);
  
  return { onlineUsers, cursors };
}
```

### 5.5 多实例支持 (Redis Pub/Sub)

当后端有多个实例时，WebSocket 消息需要通过 Redis 广播：

```python
# backend/services/ws_pubsub.py

import aioredis

class RedisPubSub:
    async def publish(self, project_id: str, message: dict):
        await self.redis.publish(f"ws:project:{project_id}", json.dumps(message))
    
    async def subscribe(self, project_id: str, callback):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"ws:project:{project_id}")
        async for message in pubsub.listen():
            if message["type"] == "message":
                await callback(json.loads(message["data"]))
```

---

## 6. 权限与项目共享

### 6.1 权限模型

```python
class ProjectMember(Base):
    __tablename__ = "project_members"
    
    id = Column(UUID, primary_key=True)
    project_id = Column(UUID, ForeignKey("projects.id"), index=True)
    user_id = Column(UUID, ForeignKey("users.id"), index=True)
    role = Column(String, nullable=False)  # owner / editor / viewer
    invited_by = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        UniqueConstraint("project_id", "user_id"),
    )
```

### 6.2 角色权限矩阵

| 操作 | Owner | Editor | Viewer |
|------|-------|--------|--------|
| 查看项目 | Y | Y | Y |
| 编辑场景/分镜 | Y | Y | N |
| 触发 AI 生成 | Y | Y | N |
| 管理成员 | Y | N | N |
| 删除项目 | Y | N | N |
| 导出项目 | Y | Y | N |
| 添加评论 | Y | Y | Y |
| 分享链接 | Y | Y | N |

### 6.3 邀请流程

```
1. Owner 点击「邀请协作者」
2. 输入对方邮箱或生成邀请链接
3. 对方点击链接 → 注册/登录 → 自动加入项目
4. Owner 可随时修改/移除成员权限
```

**API 端点:**

```
POST   /api/projects/{id}/members          # 邀请成员
GET    /api/projects/{id}/members          # 成员列表
PATCH  /api/projects/{id}/members/{uid}    # 修改角色
DELETE /api/projects/{id}/members/{uid}    # 移除成员
POST   /api/projects/{id}/invite-link      # 生成邀请链接
```

---

## 7. 数据同步与冲突解决

### 7.1 乐观锁 + Last-Write-Wins (推荐 MVP)

最简单的方案，适合初期：

```python
# 每个可编辑实体加 version 字段
class Scene(Base):
    version = Column(Integer, default=1)
    updated_at = Column(DateTime, onupdate=func.now())
    updated_by = Column(UUID, ForeignKey("users.id"))

# 更新时检查版本
def update_scene(scene_id, changes, expected_version):
    result = db.execute(
        update(Scene)
        .where(Scene.id == scene_id, Scene.version == expected_version)
        .values(**changes, version=expected_version + 1)
    )
    if result.rowcount == 0:
        raise ConflictError("数据已被其他人修改，请刷新后重试")
```

### 7.2 资源锁定 (推荐中期)

编辑时锁定资源，防止冲突：

```python
class ResourceLock(Base):
    __tablename__ = "resource_locks"
    
    resource_type = Column(String)   # scene / beat / shot
    resource_id = Column(UUID)
    locked_by = Column(UUID, ForeignKey("users.id"))
    locked_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)    # 自动过期，防止死锁
```

前端效果：其他人看到「XXX 正在编辑此场景」的提示，编辑框变为只读。

### 7.3 CRDT 实时协同编辑 (远期)

对于富文本字段（台词、描述等），使用 CRDT 库实现多人实时编辑：

| 库 | 特点 |
|-----|------|
| **Yjs** | 最流行，社区活跃，适配多种编辑器 |
| Automerge | Rust 核心，性能好 |
| Liveblocks | SaaS，开箱即用但付费 |

```typescript
// 使用 Yjs 示例
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';

const ydoc = new Y.Doc();
const provider = new WebsocketProvider(
  'wss://api.domain.com/yjs',
  `project-${projectId}-scene-${sceneId}`,
  ydoc
);

// 绑定到编辑器
const ytext = ydoc.getText('script');
// → 与 TipTap / ProseMirror / Monaco 集成
```

---

## 8. 分阶段实施路线

### Phase 1: 公网部署（1-2 周）

> 目标：任何人通过浏览器访问，单用户模式

- [ ] 创建 `backend/Dockerfile`
- [ ] 购买云服务器 + 域名
- [ ] 部署 PostgreSQL + Redis（Docker 或托管服务）
- [ ] 部署后端到 Docker
- [ ] 部署前端到 Vercel 或 Nginx
- [ ] 配置 HTTPS（Let's Encrypt）
- [ ] 配置 OSS 文件存储
- [ ] 配置生产环境变量
- [ ] 健康检查 + 基础监控

**交付物**: `https://app.unrealmake.com` 可访问

### Phase 2: 用户系统（1-2 周）

> 目标：注册登录，每人有自己的项目

- [ ] 实现 User 数据模型
- [ ] 实现 JWT 认证端点
- [ ] 前端登录/注册页面
- [ ] `fetchAPI` 自动带 token
- [ ] Project 关联 owner
- [ ] 路由守卫（未登录跳转）
- [ ] 现有 API 加认证中间件

**交付物**: 用户可注册、登录、管理自己的项目

### Phase 3: 项目共享（1 周）

> 目标：邀请他人查看/编辑项目

- [ ] ProjectMember 数据模型
- [ ] 邀请/成员管理 API
- [ ] 前端成员管理 UI
- [ ] 权限检查中间件
- [ ] 分享链接功能（升级现有骨架）

**交付物**: 可邀请他人进入项目

### Phase 4: 实时协作（2-3 周）

> 目标：多人同时在线操作

- [ ] WebSocket 端点
- [ ] 在线用户列表
- [ ] 光标/选区同步
- [ ] 操作广播（场景编辑、分镜修改）
- [ ] 资源锁定机制
- [ ] 乐观锁冲突处理
- [ ] Redis Pub/Sub（多实例支持）

**交付物**: 多人同时编辑，互相可见

### Phase 5: 深度协同（远期）

- [ ] CRDT 富文本协同编辑
- [ ] 操作历史与回滚
- [ ] @提及 + 通知系统
- [ ] 项目活动流（Activity Feed）
- [ ] 版本对比与分支

---

## 9. 安全方案

### 9.1 传输安全

- 全站 HTTPS（TLS 1.3）
- WebSocket 走 WSS
- HSTS 头部

### 9.2 认证安全

- JWT 有效期: access_token 15分钟, refresh_token 7天
- 密码 bcrypt 哈希（cost factor ≥ 12）
- 登录限流：同一 IP 5次/分钟
- refresh_token 轮转 + 黑名单

### 9.3 数据安全

- SQL 参数化查询（SQLAlchemy ORM 默认防注入）
- XSS 防护（Next.js 默认转义 + CSP 头）
- CORS 白名单（生产环境限制域名）
- 文件上传类型白名单 + 大小限制
- 敏感配置通过环境变量注入，不入代码库

### 9.4 备份

- PostgreSQL 每日自动备份（RDS 自带或 pg_dump cron）
- OSS 跨区域复制
- 保留最近 30 天备份

---

## 10. 成本估算

### 最小可行配置（5 人以下团队）

| 项目 | 月费 |
|------|------|
| ECS 2核4G | ¥100 |
| RDS PostgreSQL 1核2G | ¥80 |
| Redis 1G | ¥50 |
| OSS 10GB | ¥5 |
| 域名 | ¥4 |
| **合计** | **~¥240/月** |

### 正式运营配置（50 人以下）

| 项目 | 月费 |
|------|------|
| ECS 4核8G × 2 | ¥600 |
| RDS PostgreSQL 2核4G 高可用 | ¥300 |
| Redis 2G | ¥100 |
| OSS 100GB + CDN | ¥50 |
| SLB 负载均衡 | ¥50 |
| 域名 + SSL | ¥4 |
| **合计** | **~¥1100/月** |

### Vercel 前端（免费额度内）

- Hobby 计划: 免费（个人项目）
- Pro 计划: $20/月（团队协作）

---

## 附录：配置模板

### 后端生产环境变量 (.env.production)

```bash
# 基础
APP_ENV=production
DEBUG=false

# 数据库
DATABASE_URL=postgresql+psycopg2://unrealmake:STRONG_PASSWORD@rds-host:5432/unrealmake
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=100

# Redis
REDIS_URL=redis://:REDIS_PASSWORD@redis-host:6379/0
USE_CELERY_QUEUE=true

# 存储
STORAGE_PROVIDER=oss
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=YOUR_KEY
OSS_ACCESS_KEY_SECRET=YOUR_SECRET
OSS_BUCKET_NAME=unrealmake-prod

# AI
ANTHROPIC_API_KEY=sk-ant-xxx

# 认证 (Phase 2 新增)
JWT_SECRET=YOUR_RANDOM_64_CHAR_SECRET
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=["https://app.unrealmake.com"]

# 服务器
HOST=0.0.0.0
PORT=8000
```

### 前端生产环境变量

```bash
# packages/web/.env.production
NEXT_PUBLIC_API_URL=https://api.unrealmake.com
NEXT_PUBLIC_WS_URL=wss://api.unrealmake.com
```

### 服务器初始化脚本

```bash
#!/bin/bash
# init-server.sh — 在全新 ECS 上执行

# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# 2. 安装 Docker Compose
apt install -y docker-compose-plugin

# 3. 拉取代码
git clone https://your-repo.git /opt/unrealmake
cd /opt/unrealmake

# 4. 配置环境
cp backend/.env.production.example backend/.env.production
# 编辑 .env.production 填入实际值

# 5. 启动
docker compose -f docker-compose.production.yml up -d

# 6. 配置 SSL (Let's Encrypt)
apt install -y certbot
certbot certonly --standalone -d api.unrealmake.com
# 将证书复制到 ./certs/ 目录
```

---

## 总结

本方案从**公网部署 → 用户系统 → 项目共享 → 实时协作**四个阶段递进实施，每个阶段独立可交付。当前代码已有的 `collaboration.py` 骨架、`docker-compose.yml`、`.env.production.example` 等基础设施可以直接复用。

核心技术栈无需更换，在现有 FastAPI + Next.js 架构上扩展即可。最短路径是 Phase 1（纯部署）+ Phase 2（用户系统），即可实现多人各自使用。完整多人协作需要到 Phase 4。
