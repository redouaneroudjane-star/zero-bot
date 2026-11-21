import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=10
    )


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                network TEXT DEFAULT 'all',
                notifications BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS offers (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                network TEXT NOT NULL,
                details TEXT NOT NULL,
                conditions TEXT DEFAULT '',
                source_url TEXT NOT NULL,
                expiry TEXT DEFAULT 'غير محدد',
                status TEXT DEFAULT 'pending',
                submitted_by BIGINT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            )
        """)


def save_user(user_id, username=None, first_name=None):
    with db() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                updated_at = NOW()
        """, (user_id, username, first_name))


def set_user_network(user_id, network):
    with db() as conn:
        conn.execute("""
            UPDATE users SET network=%s, updated_at=NOW()
            WHERE user_id=%s
        """, (network, user_id))


def set_user_notifications(user_id, enabled):
    with db() as conn:
        conn.execute("""
            UPDATE users SET notifications=%s, updated_at=NOW()
            WHERE user_id=%s
        """, (enabled, user_id))


def create_offer(title, network, details, conditions,
                 source_url, expiry, submitted_by):
    with db() as conn:
        existing = conn.execute("""
            SELECT id FROM offers
            WHERE network=%s AND title=%s AND source_url=%s
            LIMIT 1
        """, (network, title, source_url)).fetchone()

        if existing:
            return None

        row = conn.execute("""
            INSERT INTO offers
            (title, network, details, conditions,
             source_url, expiry, submitted_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            title, network, details, conditions,
            source_url, expiry, submitted_by
        )).fetchone()

        return row["id"]


def get_offer(offer_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM offers WHERE id=%s",
            (offer_id,)
        ).fetchone()


def set_offer_status(offer_id, status):
    with db() as conn:
        conn.execute("""
            UPDATE offers
            SET status=%s, reviewed_at=NOW()
            WHERE id=%s
        """, (status, offer_id))


def list_pending_offers():
    with db() as conn:
        return conn.execute("""
            SELECT * FROM offers
            WHERE status='pending'
            ORDER BY created_at DESC
            LIMIT 50
        """).fetchall()


def list_approved_offers(limit=10):
    with db() as conn:
        return conn.execute("""
            SELECT * FROM offers
            WHERE status='approved'
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,)).fetchall()


def list_subscribers(network):
    with db() as conn:
        return conn.execute("""
            SELECT user_id FROM users
            WHERE notifications=TRUE
            AND (network=%s OR network='all')
        """, (network,)).fetchall()


def get_stats():
    with db() as conn:
        users = conn.execute(
            "SELECT COUNT(*) AS n FROM users"
        ).fetchone()["n"]

        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM offers WHERE status='pending'"
        ).fetchone()["n"]

        approved = conn.execute(
            "SELECT COUNT(*) AS n FROM offers WHERE status='approved'"
        ).fetchone()["n"]

        rejected = conn.execute(
            "SELECT COUNT(*) AS n FROM offers WHERE status='rejected'"
        ).fetchone()["n"]

        return {
            "users": users,
            "pending": pending,
            "approved": approved,
            "rejected": rejected
        }
