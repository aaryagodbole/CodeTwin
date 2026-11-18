"""Postgres access: one short-lived connection per request (serverless-friendly; use Neon's pooled URL) and
versioned SQL migrations applied once per process, under an advisory lock so concurrent cold starts don't race."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources

import psycopg
from psycopg.rows import DictRow, dict_row

MIGRATION_LOCK = 0x0C0D7714            # pg_advisory_xact_lock key for migrations
_migrated: set[str] = set()            # database URLs already migrated by this process


def database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (Vercel: added by the Neon integration; locally: see cloud/README.md)")
    return url


@contextmanager
def connect(url: str | None = None) -> Iterator[psycopg.Connection[DictRow]]:
    """A connection with dict rows; commits on success, rolls back on error."""
    url = url or database_url()
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10) as conn:
        if url not in _migrated:
            migrate(conn)
            _migrated.add(url)
        yield conn


def find_project(conn: psycopg.Connection[DictRow], owner: str, name: str) -> DictRow | None:
    """The project for OWNER/NAME, matched case-insensitively like GitHub. The one place projects are looked up."""
    return conn.execute("select id, owner, name, public, uploads_enabled, github_repository_id from project "
                        "where lower(owner) = lower(%s) and lower(name) = lower(%s)", (owner, name)).fetchone()


def migration_files() -> list[tuple[str, str]]:
    files = resources.files("codetwin_cloud") / "migrations"
    return sorted((f.name, f.read_text()) for f in files.iterdir() if f.name.endswith(".sql"))


def migrate(conn: psycopg.Connection[DictRow]) -> list[str]:
    """Apply migrations not applied yet, in name order, each in the same transaction as its bookkeeping row."""
    applied: list[str] = []
    with conn.transaction():
        conn.execute("select pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
        conn.execute("create table if not exists schema_migrations "
                     "(name text primary key, applied_at timestamptz not null default now())")
        done = {r["name"] for r in conn.execute("select name from schema_migrations").fetchall()}
        for name, sql in migration_files():
            if name not in done:
                conn.execute(sql.encode())  # trusted file shipped with the package
                conn.execute("insert into schema_migrations (name) values (%s)", (name,))
                applied.append(name)
    return applied
