# DEPLOYING SOLO

## Option 1 - Railway (recommended for beginners)

1. Push your code to GitHub.
2. Go to railway.app and create a new project from your GitHub repo.
3. Add a PostgreSQL database service and a Redis service from the Railway dashboard.
4. Copy the `DATABASE_URL` from Postgres service and `REDIS_URL` from Redis service into your environment variables.
5. Set these environment variables: `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`), `OPENAI_API_KEY`, `ENV=production`, `SENTRY_DSN` (optional), `ALLOWED_HOSTS=your-app-name.railway.app`.
6. Railway will build and deploy automatically using the Dockerfile.
7. The Dockerfile runs `alembic upgrade head` before starting, so your database is migrated automatically.

## Option 2 - Render

1. Push to GitHub.
2. Create a new Web Service on render.com connected to your repo.
3. Set build command: `pip install -r requirements.txt`.
4. Set start command: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. Add PostgreSQL and Redis from Render dashboard.
6. Add all environment variables in Render dashboard.

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
