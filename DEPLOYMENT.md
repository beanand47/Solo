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

1. Push to GitHub.
2. Create a new Web Service on render.com connected to your repo.
3. Set build command: `pip install -r requirements.txt`.
4. Set start command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. Add PostgreSQL and Redis from Render dashboard.
6. Add all environment variables in Render dashboard. Set `ALLOWED_HOSTS` to your Render hostname, for example `solo-e9op.onrender.com`. Render's `RENDER_EXTERNAL_HOSTNAME` is also trusted automatically when present.

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
