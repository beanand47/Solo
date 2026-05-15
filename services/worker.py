import os

from dotenv import load_dotenv
from redis import Redis
from rq import Queue


load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(REDIS_URL)
task_queue = Queue("solo_tasks", connection=redis_conn, default_timeout=120)


def get_queue():
    return task_queue
