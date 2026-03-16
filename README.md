# BabelDOC Web

基于 [BabelDOC](https://github.com/funstory-ai/BabelDOC) 核心引擎的 Web 翻译平台，提供用户友好的操作界面。

## 功能特性

- **用户管理**: 注册/登录、角色权限（管理员/普通用户）
- **文档翻译**: 上传 PDF 文档进行翻译，支持后台异步处理
- **翻译队列**: 并发控制与排队策略，避免翻译过载
- **术语表**: 创建和维护翻译术语表，提升翻译一致性
- **自定义模型**: 配置自定义翻译模型（OpenAI 兼容 API），支持 `extra_body` 自定义参数
- **管理后台**: 管理员可管理用户、查看所有任务、系统统计

## 技术栈

- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **前端**: React + Vite + Tailwind CSS
- **核心**: BabelDOC 翻译引擎

## 快速开始

### 1. 启动中间件（PostgreSQL + Redis）

```bash
docker compose up -d
```

这会启动 PostgreSQL 16 和 Redis 7，默认配置即可直连，无需额外设置。

### 2. 启动后端

```bash
cd backend

# 使用 uv 安装依赖（自动创建虚拟环境）
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置密钥等

# 启动服务
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

访问 http://localhost:5173 即可使用。

### 4. 首次使用

1. 注册第一个账户（自动成为管理员）
2. 在「模型」页面配置翻译模型（API Key 等）
3. 在「翻译」页面上传 PDF 开始翻译

## 项目结构

```
web/
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由
│   │   │   ├── auth.py       # 认证（登录/注册）
│   │   │   ├── tasks.py      # 翻译任务
│   │   │   ├── glossaries.py # 术语表
│   │   │   ├── models.py     # 自定义模型
│   │   │   └── admin.py      # 管理员接口
│   │   ├── core/         # 核心配置
│   │   │   ├── config.py     # 应用配置
│   │   │   ├── database.py   # 数据库连接
│   │   │   ├── deps.py       # 依赖注入
│   │   │   └── security.py   # 安全（JWT/密码）
│   │   ├── models/       # 数据库模型
│   │   │   └── models.py     # SQLAlchemy ORM 模型
│   │   ├── schemas/      # Pydantic Schema
│   │   │   └── schemas.py
│   │   ├── services/     # 业务服务
│   │   │   ├── queue.py          # 翻译队列
│   │   │   └── translator_worker.py # 翻译工作线程
│   │   └── main.py       # FastAPI 入口
│   ├── pyproject.toml    # uv 项目配置
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api.ts         # API 客户端
│   │   ├── auth.tsx       # 认证上下文
│   │   ├── components/
│   │   │   └── Layout.tsx # 应用布局
│   │   └── pages/
│   │       ├── LoginPage.tsx      # 登录
│   │       ├── RegisterPage.tsx   # 注册
│   │       ├── TranslatePage.tsx  # 翻译上传
│   │       ├── TasksPage.tsx      # 任务列表
│   │       ├── GlossariesPage.tsx # 术语表管理
│   │       ├── ModelsPage.tsx     # 模型管理
│   │       └── AdminPage.tsx      # 管理后台
│   └── package.json
└── README.md
```

## API 端点

### 认证
- `POST /api/auth/register` - 注册
- `POST /api/auth/login` - 登录
- `GET /api/auth/me` - 当前用户信息

### 翻译任务
- `POST /api/tasks` - 创建翻译任务（上传 PDF）
- `GET /api/tasks` - 获取我的任务列表
- `GET /api/tasks/{id}` - 获取任务详情
- `POST /api/tasks/{id}/cancel` - 取消任务
- `GET /api/tasks/{id}/download/{mono|dual}` - 下载翻译结果

### 术语表
- `GET /api/glossaries` - 术语表列表
- `POST /api/glossaries` - 创建术语表
- `PATCH /api/glossaries/{id}` - 更新术语表
- `DELETE /api/glossaries/{id}` - 删除术语表
- `POST /api/glossaries/{id}/entries` - 添加词条
- `DELETE /api/glossaries/{id}/entries/{entry_id}` - 删除词条

### 自定义模型
- `GET /api/models` - 模型列表
- `POST /api/models` - 创建模型
- `PATCH /api/models/{id}` - 更新模型
- `DELETE /api/models/{id}` - 删除模型

### 管理员
- `GET /api/admin/stats` - 系统统计
- `GET /api/admin/users` - 用户列表
- `PATCH /api/admin/users/{id}` - 更新用户
- `DELETE /api/admin/users/{id}` - 删除用户
- `GET /api/admin/tasks` - 所有任务列表
- `POST /api/admin/tasks/{id}/cancel` - 取消任务

## extra_body 自定义参数

支持在两个层级设置 `extra_body`：

1. **模型级别**: 在模型配置中设置默认的 `extra_body`，所有使用该模型的翻译任务会自动应用
2. **任务级别**: 在创建翻译任务时设置 `extra_body`，会覆盖模型配置中的同名参数

示例：

```json
{
  "reasoning": {"effort": "high"},
  "chat_template_kwargs": {"enable_thinking": false}
}
```

这些参数会直接传递给 OpenAI API 的 `extra_body` 参数，支持各种 API 提供商的自定义功能。
