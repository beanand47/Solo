# DEPLOYING SOLO

## Option 1 - Railway from scratch

1. Push this repo to GitHub.
2. In Railway, create a new project from the GitHub repo.
3. Add a PostgreSQL service.
4. Add a Redis service.
5. Open the Solo web service variables and set:

```text
ENV=production
SECRET_KEY=<generate with python -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
OPENAI_API_KEY=<your OpenAI API key>
ALLOWED_HOSTS=*
LOG_LEVEL=INFO
WEB_CONCURRENCY=1
```

Use the private/internal `DATABASE_URL` and `REDIS_URL` references. Do not use public database URLs for the web service.

6. Open the Solo web service settings, then Networking, and generate a public domain.
7. Make sure the public domain targets port `8080`.
8. Deploy the Solo web service. The Dockerfile runs `alembic upgrade head` before starting Uvicorn.
9. Verify deployment at `/health` first, then `/login`.

After the site works, replace `ALLOWED_HOSTS=*` with the exact Railway domain if you want a stricter host allowlist.

## Option 2 - Render

This repo includes a `render.yaml` Blueprint, which is the simplest way to move from Railway to Render.

### Blueprint setup

1. Push this repo to GitHub.
2. In Render, create a new Blueprint from the GitHub repo.
3. Render will create:
   - `solo` web service
   - `solo-worker` background worker
   - `solo-db` PostgreSQL database
   - `solo-redis` Render Key Value instance for Redis/RQ jobs
4. When Render asks for `OPENAI_API_KEY`, paste your key.
5. Deploy the Blueprint.
6. Open the `solo` service and verify:
   - Health check path: `/health`
   - Build command: `pip install -r requirements.txt`
   - Start command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Visit `https://<your-service>.onrender.com/health`, then `/login`.

The web service trusts Render's `RENDER_EXTERNAL_HOSTNAME` automatically, so the Blueprint keeps `ALLOWED_HOSTS` strict without needing to know the final hostname ahead of time.

### Manual dashboard setup

Use this if you do not want to use `render.yaml`.

1. Push this repo to GitHub.
2. Create a Render PostgreSQL database.
3. Create a Render Key Value instance. Use the internal connection string for the app.
4. Create a new Web Service connected to the repo:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/health`
5. Add these environment variables to the web service:

```text
ENV=production
SECRET_KEY=<generate a secret or let Render generate one>
DATABASE_URL=<Render Postgres internal connection string>
REDIS_URL=<Render Key Value internal connection string>
OPENAI_API_KEY=<your OpenAI API key>
ALLOWED_HOSTS=<your-service>.onrender.com
LOG_LEVEL=INFO
SENTRY_DSN=
```

6. Create a Background Worker connected to the same repo:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `rq worker solo_tasks`
7. Add the same `ENV`, `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `LOG_LEVEL`, and optional `SENTRY_DSN` variables to the worker.
8. Deploy the web service and worker.

Do not deploy this app with SQLite on Render. Render instances have ephemeral filesystems, so production data should live in Render Postgres or another hosted PostgreSQL provider.

## Option 3 - Docker on any VPS

1. Clone repo on your server.
2. Copy `.env.example` to `.env` and fill in all values.
3. Run: `docker-compose up -d`.
4. The app, worker, database, and Redis all start together.

## Generating a Secret Key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Checking Logs

Railway:
```bash
railway logs
```

Render: check logs tab in dashboard.

Docker:
```bash
docker-compose logs -f web
```

## Running Migrations Manually

```bash
alembic upgrade head
```

## Rolling Back a Migration

```bash
alembic downgrade -1
```
