"""SQLAlchemy engine for the admin dashboard (direct Postgres / pooler)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _uses_transaction_pooler(url: str) -> bool:
    """Supabase transaction pooler is typically :6543."""
    lowered = url.lower()
    return ":6543" in lowered or "pgbouncer=true" in lowered


@lru_cache
def get_engine() -> Optional[Engine]:
    settings = get_settings()
    url = (settings.database_url or "").strip()
    if not url:
        return None

    # Transaction-mode poolers + prepared statements / long-lived QueuePool
    # commonly cause stale/hung connections under checkout + admin load.
    if _uses_transaction_pooler(url):
        engine = create_engine(
            url,
            poolclass=NullPool,
            pool_pre_ping=True,
            future=True,
        )
        logger.info("Admin SQLAlchemy engine using NullPool (transaction pooler)")
    else:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=5,
            pool_recycle=300,
            pool_timeout=10,
            future=True,
        )
        logger.info(
            "Admin SQLAlchemy engine pool_size=3 max_overflow=5 recycle=300s"
        )
    return engine


@lru_cache
def get_session_factory():
    engine = get_engine()
    if engine is None:
        return None
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ping_admin_database() -> bool:
    engine = get_engine()
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Admin database ping failed: %s", exc, exc_info=True)
        return False
