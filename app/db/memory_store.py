"""
Persistent, per-user conversation memory.

Same behavioural contract as the original in-RAM version (last MAX_TURNS
user+assistant pairs per mobile_number), but backed by SQLite so:
  - it survives server restarts / redeploys
  - it's safe across multiple worker processes (SQLite handles the locking)

If you outgrow single-instance SQLite (e.g. move to multiple servers behind
a load balancer), swap this module for Postgres/Redis-backed storage without
touching any calling code - the get/add/clear function signatures are the
public contract.
"""
from typing import List, Dict

from app.config import settings
from app.db.database import get_connection


def get_history(mobile_number: str) -> List[Dict[str, str]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT role, content FROM conversation_turns
        WHERE mobile_number = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (mobile_number, settings.MAX_TURNS * 2),
    ).fetchall()
    # rows come back newest-first; reverse to chronological order
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def add_turn(mobile_number: str, user_query: str, bot_reply: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO conversation_turns (mobile_number, role, content) VALUES (?, 'user', ?)",
            (mobile_number, user_query),
        )
        conn.execute(
            "INSERT INTO conversation_turns (mobile_number, role, content) VALUES (?, 'assistant', ?)",
            (mobile_number, bot_reply),
        )
        # prune anything beyond the last MAX_TURNS*2 rows for this user
        conn.execute(
            """
            DELETE FROM conversation_turns
            WHERE mobile_number = ? AND id NOT IN (
                SELECT id FROM conversation_turns
                WHERE mobile_number = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (mobile_number, mobile_number, settings.MAX_TURNS * 2),
        )


def clear_history(mobile_number: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM conversation_turns WHERE mobile_number = ?", (mobile_number,))
