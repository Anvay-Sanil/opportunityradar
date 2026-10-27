"""Deduplicate both manual and scheduled jobs across worker processes."""
import uuid
from contextlib import contextmanager

from redis import Redis
from app.config import settings

LOCK_SECONDS = 1200
RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


def redis_client():
    return Redis.from_url(settings.redis_url, decode_responses=True,
                          socket_connect_timeout=2, socket_timeout=2)


@contextmanager
def job_lock(name, task_id):
    key = f"job:{name}"
    running_key = f"running:{name}"
    with redis_client() as client:
        acquired = client.set(key, task_id, nx=True, ex=LOCK_SECONDS)
        # Admin endpoints reserve the lock before putting the same task ID on the queue.
        if not acquired and client.get(key) != task_id:
            yield False
            return
        if not client.set(running_key, task_id, nx=True, ex=LOCK_SECONDS):
            yield False
            return
        client.expire(key, LOCK_SECONDS)
        try:
            yield True
        finally:
            client.eval(RELEASE, 1, running_key, task_id)
            client.eval(RELEASE, 1, key, task_id)


def enqueue_job(task, name, queue):
    task_id = str(uuid.uuid4())
    key = f"job:{name}"
    with redis_client() as client:
        if not client.set(key, task_id, nx=True, ex=LOCK_SECONDS):
            return client.get(key), False
        try:
            task.apply_async(task_id=task_id, queue=queue, expires=LOCK_SECONDS)
        except Exception:
            client.eval(RELEASE, 1, key, task_id)
            raise
    return task_id, True
