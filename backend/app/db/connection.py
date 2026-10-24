from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


class DatabaseNotConfigured(RuntimeError):
    pass


def _connect(*, row_factory: Any = None) -> Any:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    import psycopg

    return psycopg.connect(database_url, connect_timeout=10, row_factory=row_factory)


def test_connection() -> tuple[str, datetime]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT NOW() AS database_time, current_database() AS database_name"
        ).fetchone()
    return row[1], row[0]


def apply_schema() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema = schema_path.read_text(encoding="utf-8")
    with _connect() as connection:
        for statement in schema.split(";"):
            if statement.strip():
                connection.execute(statement)
        migrations = schema_path.parent / "migrations"
        if migrations.exists():
            for migration in sorted(migrations.glob("*.sql")):
                for statement in migration.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        connection.execute(statement)
