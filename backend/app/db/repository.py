"""Shared PostgreSQL transaction boundary for application services."""
from contextlib import contextmanager
from typing import Any, Iterator

from app.db.connection import _connect


@contextmanager
def transaction() -> Iterator[Any]:
    from psycopg.rows import dict_row

    with _connect(row_factory=dict_row) as connection:
        yield connection


@contextmanager
def read_connection() -> Iterator[Any]:
    from psycopg.rows import dict_row

    with _connect(row_factory=dict_row) as connection:
        yield connection
