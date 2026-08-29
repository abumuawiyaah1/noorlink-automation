"""Direct Postgres access for the admin dashboard."""

from app.db.engine import get_engine, get_session_factory, ping_admin_database

__all__ = ["get_engine", "get_session_factory", "ping_admin_database"]
