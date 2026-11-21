
"""Database layer for ZERO-BOT."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("SQLITE_PATH", "zero_bot.db")


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with get_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                network TEXT,
                notifications_enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                network TEXT NOT NULL,
                details TEXT,
                price TEXT,
                duration TEXT,
                eligibility TEXT,
                source_url TEXT NOT NULL,
                expires_at TEXT,
                status TEXT DEFAULT 'pending',
                fingerprint TEXT UNIQUE NOT NULL,
                submitted_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_user(telegram_id, username=None, first_name=None, network=None):
    with get_connection() as db:
        db.execute("""
            INSERT INTO users (telegram_id, username, first_name, network)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                network = COALESCE(excluded.network, users.network)
        """, (telegram_id, username, first_name, network))


def save_offer(title, network, source_url, fingerprint,
               details=None, price=None, duration=None,
               eligibility=None, expires_at=None, submitted_by=None):
    with get_connection() as db:
        cursor = db.execute("""
            INSERT OR IGNORE INTO offers (
                title, network, details, price, duration,
                eligibility, source_url, expires_at,
                fingerprint, submitted_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, network, details, price, duration,
            eligibility, source_url, expires_at,
            fingerprint, submitted_by
        ))
        return cursor.rowcount > 0


def list_pending_offers(limit=50):
    with get_connection() as db:
        rows = db.execute("""
            SELECT * FROM offers
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT ?
        """, (max(1, min(int(limit), 200)),)).fetchall()
        return [dict(row) for row in rows]


def set_offer_status(offer_id, status):
    if status not in ("approved", "rejected", "pending"):
        raise ValueError("Invalid offer status")

    with get_connection() as db:
        cursor = db.execute(
            "UPDATE offers SET status = ? WHERE id = ?",
            (status, offer_id)
        )
        return cursor.rowcount > 0
