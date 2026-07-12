import sqlite3
import threading

from app.config import settings

_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def get_connection() -> sqlite3.Connection:
    """One connection per thread (FastAPI runs sync endpoints in a thread pool).
    WAL mode lets concurrent readers/writers coexist safely for our traffic level."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        conn = get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mobile_number TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_mobile ON conversation_turns(mobile_number, id);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rate_limit_buckets (
                mobile_number TEXT PRIMARY KEY,
                window_start REAL NOT NULL,
                request_count INTEGER NOT NULL
            );
            """
        )
        conn.commit()
        _initialized = True
