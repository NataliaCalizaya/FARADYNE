import json
import logging
import sys
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from app.core.config import settings

logger = logging.getLogger("faradyne.database")
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)

db_pool: Optional[ThreadedConnectionPool] = None


def init_db_pool() -> None:
    """Initialize PostgreSQL connection pool and verify connection on startup."""
    global db_pool
    try:
        logger.info(
            f"Connecting to PostgreSQL DB '{settings.DB_NAME}' at {settings.DB_HOST}:{settings.DB_PORT} as '{settings.DB_USER}'..."
        )
        db_pool = ThreadedConnectionPool(
            minconn=settings.DB_MIN_CONN,
            maxconn=settings.DB_MAX_CONN,
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            dbname=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        # Test initial connection
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            result = cur.fetchone()
            logger.info(f"Database connection successful (SELECT 1 returned {result}).")
        db_pool.putconn(conn)
    except Exception as e:
        logger.critical(f"FATAL: Database connection failed: {e}")
        logger.critical("Exiting server due to initial database connection failure.")
        sys.exit(1)


def close_db_pool() -> None:
    """Close PostgreSQL connection pool gracefully."""
    global db_pool
    if db_pool:
        logger.info("Closing database connection pool...")
        db_pool.closeall()
        db_pool = None


@contextmanager
def get_db_cursor(commit: bool = False):
    """Context manager to acquire connection from pool, yield RealDictCursor, handle commit/rollback, and return connection."""
    global db_pool
    if db_pool is None:
        init_db_pool()

    conn = db_pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database query error: {e}")
        raise e
    finally:
        db_pool.putconn(conn)


def fetch_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """Execute parameterized SELECT query and return one dictionary row or None."""
    with get_db_cursor(commit=False) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute parameterized SELECT query and return list of dictionary rows."""
    with get_db_cursor(commit=False) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def execute_query(query: str, params: tuple = (), fetch: bool = False) -> Optional[Dict[str, Any]]:
    """Execute parameterized INSERT/UPDATE/DELETE query with commit."""
    with get_db_cursor(commit=True) as cur:
        cur.execute(query, params)
        if fetch:
            row = cur.fetchone()
            return dict(row) if row else None
        return None


def serialize_json(data: Any) -> str:
    """Helper to serialize dicts/lists to JSON string for PostgreSQL JSONB columns."""
    return json.dumps(data, ensure_ascii=False)
