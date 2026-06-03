# ForYou — FastAPI Backend v2.0

Production-ready FastAPI backend for the **ForYou** project gallery platform.
Runs on **port 8081** — matches the frontend's `VITE_API_BASE_URL` default.

---

## Stack

| Layer | Tech |
|---|---|
| Framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Database | MySQL 8 (Aiven cloud) |
| Validation | Pydantic v2 |
| Server | Uvicorn |
| SSL | PyMySQL + CA cert |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                  ← App, CORS, middleware, routers
│   ├── config/settings.py       ← Pydantic settings from .env
│   ├── db/database.py           ← Engine, session, Base (SSL support)
│   ├── models/project.py        ← SQLAlchemy ORM model
│   ├── schemas/project.py       ← Pydantic request/response schemas
│   ├── repositories/            ← Raw DB queries only
│   ├── services/                ← Business logic only
│   ├── api/routes/templates.py  ← All 10 API endpoints
│   └── middleware/error_handler.py
├── alembic/                     ← Migration scripts
├── ssl/ca.pem                   ← Aiven SSL certificate
├── tests/                       ← 20+ pytest tests
├── run.py                       ← Dev server entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env
```

---

## Quick Start

### 1. Install dependencies
```cmd
py -m pip install -r requirements.txt
```

### 2. Configure .env
```
DB_HOST=mysql-a6e6252-elenah-f5fd.i.aivencloud.com
DB_PORT=18767
DB_USER=avnadmin
DB_PASSWORD=your_password
DB_NAME=defaultdb
DB_SSL_CA=ssl/ca.pem
DB_FALLBACK_SQLITE=False
APP_PORT=8081
```

> Note: `DB_FALLBACK_SQLITE` is disabled by default so production failures surface immediately. Enable it only for local development when you want a lightweight fallback.
>
> If only the MySQL database is down, `/health/db` will show a focused database diagnostic message while the rest of the API is still running.

### 3. Run migrations
```cmd
py -m alembic upgrade head
```

### 4. Start server
```cmd
py run.py
```

- API: http://localhost:8081/api/templates
- Docs: http://localhost:8081/docs
- Health: http://localhost:8081/health
- DB diagnostic: http://localhost:8081/health/db

> If only database connectivity is failing, use `/health/db` to verify MySQL credentials, SSL CA path, and network access.

---

## API Endpoints

| Method | Endpoint | Frontend caller | Description |
|---|---|---|---|
| GET | `/api/templates` | AdminProjects, SearchExplore | All projects |
| GET | `/api/templates/{id}` | ProjectDetails | Single project |
| POST | `/api/templates` | AddProject | Create (→ PENDING) |
| PUT | `/api/templates/{id}` | AdminProjects edit | Update |
| DELETE | `/api/templates/{id}` | AdminProjects | Soft delete |
| PUT | `/api/templates/{id}/approve` | AdminProjects | Approve |
| PUT | `/api/templates/{id}/reject` | AdminProjects | Reject |
| GET | `/api/templates/search?projectName=` | SearchExplore | Name search |
| GET | `/api/templates/filter?accessType=` | SearchExplore | FREE/PAID filter |
| GET | `/api/templates/filter?status=APPROVED` | Home | Public gallery |

---

## Run Tests

```cmd
py -m pytest tests/ -v
```

Uses SQLite in-memory — no MySQL needed for tests.

---

## Alembic Commands

```cmd
py -m alembic upgrade head        # apply all migrations
py -m alembic revision --autogenerate -m "description"  # new migration
py -m alembic downgrade -1        # rollback one step
py -m alembic current             # check current version
```

---

## Docker

```cmd
docker-compose up --build
```

Starts MySQL + backend together. Backend on port 8081.
