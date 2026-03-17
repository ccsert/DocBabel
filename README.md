# BabelDOC Web

[简体中文](README.zh-CN.md) | English

A web platform for PDF document translation, powered by the [BabelDOC](https://github.com/funstory-ai/BabelDOC) engine. It provides user management, model configuration, task queuing, glossary management, offline asset operations, and an admin console.

## Screenshots

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/images/readme/login-page.png" width="100%" alt="Login page" />
      <br /><em>Login</em>
    </td>
    <td width="50%" align="center">
      <img src="docs/images/readme/translate-dashboard.png" width="100%" alt="Translation dashboard" />
      <br /><em>Translate</em>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/images/readme/translate-advanced.png" width="100%" alt="Advanced translation options" />
      <br /><em>Advanced Options</em>
    </td>
    <td width="50%" align="center">
      <img src="docs/images/readme/tasks-page.png" width="100%" alt="Tasks page" />
      <br /><em>Tasks</em>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/images/readme/files-page.png" width="100%" alt="File library" />
      <br /><em>File Library</em>
    </td>
    <td width="50%" align="center">
      <img src="docs/images/readme/glossaries-page.png" width="100%" alt="Glossary management" />
      <br /><em>Glossaries</em>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/images/readme/models-page.png" width="100%" alt="Model configuration" />
      <br /><em>Models</em>
    </td>
    <td width="50%" align="center">
      <img src="docs/images/readme/admin-page.png" width="100%" alt="Admin dashboard" />
      <br /><em>Admin</em>
    </td>
  </tr>
</table>

## Features

- **User system** — Sign-up, sign-in, admin roles, and access separation
- **Translation tasks** — Create, queue, cancel, download, and track PDF translation jobs
- **Glossary management** — Maintain glossaries and save automatically extracted terms
- **Model configuration** — OpenAI-compatible model setup with `extra_body` pass-through
- **Offline assets** — Restore, check, export, and validate with profile-based preflight
- **Admin console** — System stats, user management, and global task overview

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | FastAPI, SQLAlchemy, PostgreSQL, Alembic |
| Frontend | React, Vite, Tailwind CSS |
| Queue & Cache | Redis |
| Translation | BabelDOC |

## Quick Start

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts PostgreSQL and Redis with the default local setup.

### 2. Start backend

```bash
cd backend

uv sync
uv run alembic upgrade head
cp .env.example .env
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Start frontend

```bash
cd frontend

npm install
npm run dev
```

By default, the frontend runs at `http://localhost:5173` and the backend at `http://localhost:8000`.

## First Run

1. Register the first account — it automatically becomes the admin.
2. Add at least one translation model on the **Models** page.
3. Upload a PDF and submit a task on the **Translate** page.
4. Track progress and download results on the **Tasks** page.

## Features in Detail

### Translation Workflow

- Upload a PDF and choose source/target language, model, and glossary.
- Produce bilingual or monolingual output files.
- Save automatically extracted terms into reusable glossaries.

### Admin Console

- View total users, total tasks, running tasks, and queued tasks.
- Manage users and global tasks.
- Inspect offline asset readiness and trigger restore or export actions.

### Offline Deployment

Environment variables:

| Variable | Description |
|----------|-------------|
| `BABELDOC_OFFLINE_MODE=true` | Enable offline mode |
| `BABELDOC_OFFLINE_ASSETS_PACKAGE=/path/to/pkg.zip` | Path to offline assets package |
| `BABELDOC_PRECHECK_ASSETS_ON_STARTUP=true` | Run asset pre-check on startup |
| `BABELDOC_OFFLINE_ASSET_PROFILE=full\|core\|minimal` | Asset profile level |

Profile guidance:

| Profile | Use Case |
|---------|----------|
| `full` | Strict offline environments |
| `core` | Development and integration testing |
| `minimal` | Minimal startup validation only |

## Project Structure

```
web/
├── backend/
│   ├── app/
│   │   ├── api/          # Auth, tasks, glossaries, models, admin
│   │   ├── core/         # Config, database, deps, security
│   │   ├── models/       # ORM models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Queue, translator worker, asset services
│   │   └── main.py       # FastAPI entry point
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── api.ts
│   │   ├── auth.tsx
│   │   └── App.tsx
│   └── package.json
├── docs/
├── docker-compose.yml
├── LICENSE
└── README.md
```

## API Reference

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Log in |
| GET | `/api/auth/me` | Get current user info |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/tasks` | Create a translation task |
| GET | `/api/tasks` | List tasks |
| GET | `/api/tasks/{id}` | Get task details |
| POST | `/api/tasks/{id}/cancel` | Cancel a task |
| GET | `/api/tasks/{id}/download/{mono\|dual}` | Download output |
| POST | `/api/tasks/{id}/save-glossary` | Save extracted glossary |

### Glossaries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/glossaries` | List glossaries |
| POST | `/api/glossaries` | Create a glossary |
| PATCH | `/api/glossaries/{id}` | Update a glossary |
| DELETE | `/api/glossaries/{id}` | Delete a glossary |
| POST | `/api/glossaries/{id}/entries` | Add an entry |
| DELETE | `/api/glossaries/{id}/entries/{entry_id}` | Delete an entry |

### Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/models` | List models |
| POST | `/api/models` | Create a model |
| PATCH | `/api/models/{id}` | Update a model |
| DELETE | `/api/models/{id}` | Delete a model |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/stats` | System statistics |
| GET | `/api/admin/users` | List users |
| PATCH | `/api/admin/users/{id}` | Update a user |
| DELETE | `/api/admin/users/{id}` | Delete a user |
| GET | `/api/admin/tasks` | List all tasks |
| POST | `/api/admin/tasks/{id}/cancel` | Cancel any task |
| GET | `/api/admin/offline-assets/status` | Asset status |
| POST | `/api/admin/offline-assets/check` | Check assets |
| POST | `/api/admin/offline-assets/restore` | Restore assets |
| POST | `/api/admin/offline-assets/export` | Export assets |
| GET | `/api/admin/offline-assets/export/download` | Download export |

## `extra_body` Support

The platform supports `extra_body` at both the model-default level and the per-task override level.

```json
{
  "reasoning": { "effort": "high" },
  "chat_template_kwargs": { "enable_thinking": false }
}
```

## License

This project is licensed under [AGPL-3.0](LICENSE), aligned with its runtime dependency [BabelDOC](https://github.com/funstory-ai/BabelDOC).

> **Note:** The backend pins `babeldoc==0.5.23` in [backend/pyproject.toml](backend/pyproject.toml). If you deploy this project as a network service, redistribute it, or publish modified versions, review the license obligations inherited from BabelDOC and its third-party dependencies. This is an engineering compliance reminder, not legal advice.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Roadmap

- [ ] Production deployment docs and reverse-proxy examples
- [ ] Third-party dependency license notice
- [ ] Docker-first quick-start guide
