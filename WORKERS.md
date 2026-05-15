# Background Workers

Solo uses RQ with Redis for slow AI operations such as generating onboarding briefs.

## Starting The Worker Locally

1. Install and start Redis.

   Mac:

   ```bash
   brew install redis
   brew services start redis
   ```

   Docker:

   ```bash
   docker run -d -p 6379:6379 redis
   ```

2. In one terminal:

   ```bash
   uvicorn main:app --reload
   ```

3. In another terminal:

   ```bash
   rq worker solo_tasks
   ```

The worker processes background jobs automatically. If Redis is not running, the app still works, but AI brief generation falls back to direct generation inside the request and logs a warning.
