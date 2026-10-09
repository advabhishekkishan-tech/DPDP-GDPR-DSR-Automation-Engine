"""Database connections for local SQLite and hosted PostgreSQL.

This module opens connections only. Schema changes belong in migrations.py.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


def _sqlite_connect():
    conn = sqlite3.connect(BASE_DIR / "privacyops.db", timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.row_factory = sqlite3.Row
    return conn


class PostgresConnection:
    """Small compatibility adapter for the app's existing DB-API call sites."""

    def __init__(self, connection: Any):
        self._connection = connection

    def execute(self, sql: str, params=()):
        statement = sql.strip()
        if statement.upper().startswith("INSERT OR IGNORE INTO "):
            statement = statement.replace("INSERT OR IGNORE INTO ", "INSERT INTO ", 1)
            statement = statement.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        statement = statement.replace("?", "%s")
        cursor = self._connection.cursor()
        cursor.execute(statement, params)
        return cursor

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()


def connect():
    """Return a connection for the configured backend."""
    if not DATABASE_URL:
        return _sqlite_connect()
    if not IS_POSTGRES:
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL URL beginning postgres:// or postgresql://."
        )
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. Install project requirements."
        ) from exc
    connection = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
    return PostgresConnection(connection)
