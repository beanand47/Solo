# Database Setup

## Local Development

1. Leave `DATABASE_URL` as SQLite in `.env`.
2. Run:
   ```bash
   alembic upgrade head
   ```
3. Run:
   ```bash
   uvicorn main:app --reload
   ```

## Production With PostgreSQL

1. Create a Postgres database on Railway, Render, Supabase, or Neon.
2. Copy the connection string they give you.
3. Set `DATABASE_URL=postgresql://...` in your production environment.
4. Run:
   ```bash
   alembic upgrade head
   ```
5. Start the app.

## Adding A New Model Field

1. Edit `models.py`.
2. Run:
   ```bash
   alembic revision --autogenerate -m "describe your change"
   ```
3. Run:
   ```bash
   alembic upgrade head
   ```

Never edit migration files that have already been applied to production.
