"""
Simple fixed-window rate limiter, keyed by mobile_number, persisted in SQLite
so it's shared across worker processes on a single instance.

For ~100 users this is plenty. If you later scale to multiple instances
behind a load balancer, swap this for a Redis-backed limiter (same
function signature) without touching the routers.
"""
import time

from fastapi import HTTPException, status

from app.config import settings
from app.db.database import get_connection

WINDOW_SECONDS = 60


def check_rate_limit(mobile_number: str) -> None:
    conn = get_connection()
    now = time.time()

    with conn:
        row = conn.execute(
            "SELECT window_start, request_count FROM rate_limit_buckets WHERE mobile_number = ?",
            (mobile_number,),
        ).fetchone()

        if row is None or (now - row["window_start"]) >= WINDOW_SECONDS:
            conn.execute(
                """
                INSERT INTO rate_limit_buckets (mobile_number, window_start, request_count)
                VALUES (?, ?, 1)
                ON CONFLICT(mobile_number) DO UPDATE SET window_start = excluded.window_start, request_count = 1
                """,
                (mobile_number, now),
            )
            return

        if row["request_count"] >= settings.RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({settings.RATE_LIMIT_PER_MINUTE} requests/minute). Please slow down.",
            )

        conn.execute(
            "UPDATE rate_limit_buckets SET request_count = request_count + 1 WHERE mobile_number = ?",
            (mobile_number,),
        )
