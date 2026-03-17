# BabelDOC Web — 部署指南

## 目录

- [1. 环境要求](#1-环境要求)
- [2. 快速部署（开发环境）](#2-快速部署开发环境)
- [3. 生产环境部署](#3-生产环境部署)
- [4. 环境变量配置](#4-环境变量配置)
- [5. 数据库迁移](#5-数据库迁移)
- [6. 离线环境部署](#6-离线环境部署)
- [7. 常见问题排查](#7-常见问题排查)

---

## 1. 环境要求

### 1.1 基础环境

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| **Python** | >= 3.10, < 3.14 | 后端运行环境 |
| **Node.js** | >= 18 | 前端构建 |
| **PostgreSQL** | >= 14 | 主数据库 |
| **Redis** | >= 6 (可选) | 缓存与扩展 |

### 1.2 Python 依赖

核心依赖包括：
- `fastapi` — Web 框架
- `uvicorn` — ASGI 服务器
- `sqlalchemy[asyncio]` + `asyncpg` — 异步数据库访问
- `alembic` — 数据库迁移
- `babeldoc` — PDF 翻译核心引擎
- `python-jose` + `bcrypt` — 认证安全
- `openai` + `httpx` — 模型 API 调用

---

## 2. 快速部署（开发环境）

### 2.1 启动中间件

使用 Docker Compose 启动 PostgreSQL 和 Redis：

```bash
cd web/
docker compose up -d
```

这将启动：
- PostgreSQL：`localhost:5432`（用户名/密码/数据库: `babeldoc`)
- Redis：`localhost:6379`

### 2.2 安装后端依赖

```bash
cd web/backend

# 使用 uv（推荐）
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 2.3 初始化数据库

```bash
cd web/backend
alembic upgrade head
```

### 2.4 启动后端服务

```bash
cd web/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后：
- API 地址：`http://localhost:8000`
- 健康检查：`http://localhost:8000/api/health`
- API 文档：`http://localhost:8000/docs`（Swagger UI）

### 2.5 安装前端依赖

```bash
cd web/frontend
npm install
```

### 2.6 启动前端服务

```bash
cd web/frontend
npm run dev
```

前端默认运行在 `http://localhost:5173`。

### 2.7 首次使用

1. 访问 `http://localhost:5173/register` 注册第一个用户（自动成为管理员）
2. 登录后进入「模型」页面，配置翻译模型（API Key、Base URL 等）
3. 上传 PDF 开始翻译

---

## 3. 生产环境部署

### 3.1 前端构建

```bash
cd web/frontend
npm run build
```

构建产物在 `dist/` 目录，使用 Nginx 或其他 Web 服务器托管。

### 3.2 Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 文件上传超时
        proxy_read_timeout 600s;
        client_max_body_size 100M;
    }
}
```

### 3.3 后端生产启动

```bash
cd web/backend
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
```

> 注意：由于翻译队列使用了进程内 `asyncio.Queue`，建议 workers 设置为 **1**。如需水平扩展，请使用 Redis 队列替代。

### 3.4 使用 systemd 管理

创建 `/etc/systemd/system/babeldoc-web.service`：

```ini
[Unit]
Description=BabelDOC Web Backend
After=network.target postgresql.service

[Service]
Type=simple
User=babeldoc
WorkingDirectory=/opt/babeldoc-web/backend
Environment="DATABASE_URL=postgresql+asyncpg://babeldoc:YOUR_PASSWORD@localhost:5432/babeldoc"
Environment="SECRET_KEY=YOUR_SECURE_RANDOM_KEY"
ExecStart=/opt/babeldoc-web/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable babeldoc-web
sudo systemctl start babeldoc-web
```

---

## 4. 环境变量配置

所有配置项可通过环境变量覆盖：

### 4.1 基础配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `APP_NAME` | `BabelDOC Web` | 应用名称 |
| `DEBUG` | `false` | 调试模式 |
| `SECRET_KEY` | `change-me-...` | **必须修改**，JWT 签名密钥，使用长随机字符串 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Token 有效期（分钟） |

### 4.2 数据库配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `postgresql+asyncpg://babeldoc:babeldoc@localhost:5432/babeldoc` | PostgreSQL 连接地址 |

### 4.3 文件存储配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `UPLOAD_DIR` | `app/uploads` | PDF 上传文件存储目录 |
| `OUTPUT_DIR` | `app/outputs` | 翻译结果输出目录 |
| `BABELDOC_OFFLINE_EXPORT_DIR` | `app/outputs/offline-assets` | 离线包导出目录 |

### 4.4 翻译队列配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MAX_CONCURRENT_TRANSLATIONS` | `2` | 最大同时翻译任务数 |
| `MAX_QUEUE_SIZE` | `100` | 翻译队列最大容量 |
| `DEFAULT_QPS` | `4` | 翻译 API 默认每秒请求数 |

### 4.5 离线模式配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BABELDOC_OFFLINE_MODE` | `false` | 是否启用离线模式 |
| `BABELDOC_OFFLINE_ASSETS_PACKAGE` | `null` | 离线资源包路径 (ZIP)，设置后启动时自动恢复 |
| `BABELDOC_PRECHECK_ASSETS_ON_STARTUP` | `false` | 启动时是否预检查资源完整性 |
| `BABELDOC_OFFLINE_ASSET_PROFILE` | `full` | 资源检查 profile: `full` / `core` / `minimal` |

---

## 5. 数据库迁移

### 5.1 执行迁移

```bash
cd web/backend
alembic upgrade head
```

### 5.2 迁移版本记录

| 版本 | 说明 |
|------|------|
| `20260315_0000` | 初始 schema：users, translation_tasks, glossary_sets, glossary_entries, custom_models |
| `20260316_0001` | 添加自动术语提取字段 (auto_extract_glossary, extracted_glossary_data) |
| `20260316_0002` | 添加去重哈希字段 (file_hash, model_config_hash) |
| `20260316_0003` | 添加任务耗时字段、协作术语表支持 (glossary_contributions) |

### 5.3 回滚迁移

```bash
# 回滚到上一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade 20260316_0002
```

---

## 6. 离线环境部署

### 6.1 准备阶段（联网环境）

1. **正常部署并启动系统**
2. **登录管理员账号** → 进入「管理」→「仪表盘」
3. **点击「预热并导出离线包」**，等待资源下载和打包完成
4. **点击「下载最新离线包」** 获取 ZIP 文件（约 200+ MB）
5. 同时准备好：
   - Python 环境及所有 pip 依赖的离线包 (`pip download -d packages -r requirements.txt`)
   - Node.js 及前端构建产物（或连同 `node_modules` 一起打包）
   - PostgreSQL 安装包
   - 项目源代码

### 6.2 部署阶段（离线环境）

1. **安装 PostgreSQL**，创建数据库和用户
2. **安装 Python 环境**，安装依赖包（使用离线 pip 包）
3. **部署项目代码**
4. **配置环境变量**：

```bash
export DATABASE_URL="postgresql+asyncpg://babeldoc:password@localhost:5432/babeldoc"
export SECRET_KEY="your-secure-random-key"
export BABELDOC_OFFLINE_MODE=true
export BABELDOC_OFFLINE_ASSETS_PACKAGE="/path/to/offline_assets.zip"
export BABELDOC_PRECHECK_ASSETS_ON_STARTUP=true
export BABELDOC_OFFLINE_ASSET_PROFILE=full
```

5. **执行数据库迁移**：

```bash
cd web/backend
alembic upgrade head
```

6. **启动后端服务**：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动时系统会自动从 `BABELDOC_OFFLINE_ASSETS_PACKAGE` 路径恢复离线资源包。

7. **部署前端（使用预构建的 dist 目录）**

### 6.3 验证离线部署

- 访问 `http://server:8000/api/health` 检查健康状态
- 登录管理后台 → 仪表盘 → 查看「离线资源状态」确认所有资源就绪
- 提交一个测试翻译任务验证端到端流程

---

## 7. 常见问题排查

### 7.1 后端无法启动

**错误：ModuleNotFoundError: No module named 'babeldoc'**
```bash
# 安装 babeldoc 依赖
uv pip install babeldoc
# 或
pip install babeldoc
```

**错误：无法连接数据库**
- 检查 PostgreSQL 是否运行：`docker compose ps`
- 检查 `DATABASE_URL` 环境变量是否正确
- 确保 `alembic upgrade head` 已执行

### 7.2 翻译任务一直排队

- 检查 `MAX_CONCURRENT_TRANSLATIONS` 设置，增大并发数
- 查看后端日志确认 worker 是否正常运行
- 检查模型 API Key 是否有效

### 7.3 前端无法访问后端 API

- 确认后端运行在正确端口
- 检查 Vite 配置中的代理设置（开发模式）
- 生产环境检查 Nginx 反向代理配置
- 确认 CORS 设置允许前端域名

### 7.4 离线资源不完整

- 登录管理后台查看缺失资源列表
- 重新在联网环境「预热并导出」
- 确认离线包传输完整（检查文件大小）
- 确认 `BABELDOC_OFFLINE_ASSET_PROFILE` 设置正确

### 7.5 PDF 翻译输出异常

- 检查 PDF 是否为扫描件，如是则启用 OCR 模式
- 检查模型 API Key 余额和可用性
- 尝试切换不同的翻译模型
- 检查 extra_body 参数格式是否为合法 JSON
