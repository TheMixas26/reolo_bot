#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import asyncpg

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import config as project_config  # type: ignore
except Exception:
    project_config = None

TABLES = [
    "user_accounts",
    "birthdays",
    "rpg_players",
    "achievements",
    "user_achievements",
    "cards",
    "card_packs",
    "inventory",
    "card_events",
    "card_event_rewards",
    "scheduled_posts",
]

OPTIONAL_TABLES = {"scheduled_posts"}
UPSERT_KEYS_BY_TABLE = {
    "user_accounts": ("user_id",),
    "birthdays": ("user_id",),
    "rpg_players": ("user_id",),
    "achievements": ("id",),
    "user_achievements": ("user_id", "achievement_id"),
    "cards": ("id",),
    "card_packs": ("id",),
    "inventory": ("user_id", "card_id"),
    "card_events": ("id",),
    "card_event_rewards": ("event_id", "user_id"),
    "scheduled_posts": ("id",),
}

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS user_accounts (
    user_id BIGINT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    balance DOUBLE PRECISION NOT NULL DEFAULT 0,
    post_counter INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS birthdays (
    user_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    personal_notify BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS rpg_players (
    user_id BIGINT PRIMARY KEY,
    cls TEXT NOT NULL,
    race TEXT NOT NULL,
    hp INTEGER NOT NULL,
    level INTEGER NOT NULL,
    atk INTEGER NOT NULL,
    defn INTEGER NOT NULL,
    dodge DOUBLE PRECISION NOT NULL,
    inventory_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS achievements (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    conditions TEXT
);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id BIGINT NOT NULL,
    achievement_id INTEGER NOT NULL,
    obtained_at BIGINT,
    PRIMARY KEY (user_id, achievement_id),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    rarity TEXT NOT NULL,
    hp INTEGER NOT NULL,
    atk INTEGER NOT NULL,
    def INTEGER NOT NULL,
    type TEXT,
    category TEXT,
    ability TEXT,
    image TEXT,
    "desc" TEXT
);

CREATE TABLE IF NOT EXISTS card_packs (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    price INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS inventory (
    user_id BIGINT NOT NULL,
    card_id INTEGER NOT NULL,
    amount INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, card_id)
);

CREATE TABLE IF NOT EXISTS card_events (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    reward INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
    closed_at BIGINT
);

CREATE TABLE IF NOT EXISTS card_event_rewards (
    event_id INTEGER NOT NULL,
    user_id BIGINT NOT NULL,
    rewarded_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
    PRIMARY KEY (event_id, user_id)
);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id BIGSERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    content_type TEXT NOT NULL,
    publish_at TIMESTAMP,
    is_question BOOLEAN NOT NULL,
    is_anonymous BOOLEAN NOT NULL,
    source_user_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_by BIGINT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


def resolve_postgres_dsn(explicit: str | None) -> str:
    if explicit:
        return explicit

    env_value = os.getenv("DATABASE_URL")
    if env_value:
        return env_value

    if project_config is not None:
        for name in ("DATABASE_URL", "POSTGRES_DSN"):
            value = getattr(project_config, name, None)
            if value:
                return value

    return "postgresql://postgres:postgres@localhost:5432/reolo_bot"


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def normalize_sqlite_value(value: Any, column_name: str | None = None, column_type: str | None = None) -> Any:
    if value is None:
        return None

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    type_name = (column_type or "").upper()
    boolish_name = bool(column_name) and (
        column_name.lower().startswith("is_")
        or column_name.lower() in {"personal_notify", "is_active", "is_question", "is_anonymous"}
    )

    if isinstance(value, int) and ("BOOL" in type_name or boolish_name):
        return bool(value)

    if isinstance(value, str) and ("BOOL" in type_name or boolish_name):
        lowered = value.strip().lower()
        if lowered in {"0", "1"}:
            return lowered == "1"
        if lowered in {"true", "false"}:
            return lowered == "true"

    return value


async def migrate_table(postgres_conn: asyncpg.Connection, sqlite_conn: sqlite3.Connection, table_name: str) -> int:
    cursor = sqlite_conn.execute(f'SELECT * FROM "{table_name}"')
    rows = cursor.fetchall()
    if not rows:
        return 0

    columns = [description[0] for description in cursor.description]
    column_types = {
        row[1]: (row[2] or "").upper()
        for row in sqlite_conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }
    pk_columns = UPSERT_KEYS_BY_TABLE.get(table_name, (columns[0],)) if columns else ()
    normalized_rows = []

    for row in rows:
        normalized_row = []
        for value, col_name in zip(row, columns):
            normalized_row.append(normalize_sqlite_value(value, col_name, column_types.get(col_name)))
        normalized_rows.append(tuple(normalized_row))

    quoted_columns = [quote_ident(col) for col in columns]
    placeholder_list = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    insert_columns_sql = ", ".join(quoted_columns)
    conflict_columns_sql = ", ".join(quote_ident(col) for col in pk_columns)
    update_columns = [
        f"{quote_ident(col)} = EXCLUDED.{quote_ident(col)}"
        for col in columns
        if col not in pk_columns
    ]
    if not update_columns:
        update_columns = [f"{quote_ident(columns[0])} = EXCLUDED.{quote_ident(columns[0])}"]
    query = (
        f"INSERT INTO {quote_ident(table_name)} ({insert_columns_sql}) "
        f"VALUES ({placeholder_list}) "
        f"ON CONFLICT ({conflict_columns_sql}) DO UPDATE SET {', '.join(update_columns)}"
    )
    await postgres_conn.executemany(query, normalized_rows)
    return len(normalized_rows)


async def migrate(sqlite_path: str, postgres_dsn: str, reset: bool = False) -> None:
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        sqlite_tables = {
            row[0] for row in sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        }

        tables_to_migrate = [table for table in TABLES if table in sqlite_tables]
        if not tables_to_migrate:
            raise RuntimeError("No supported tables found in SQLite database")

        missing_optional = [table for table in OPTIONAL_TABLES if table not in sqlite_tables]
        if missing_optional:
            print(f"[INFO] Optional tables not found in SQLite, skipping: {missing_optional}")

        postgres_conn = await asyncpg.connect(postgres_dsn)
        try:
            if reset:
                for table in reversed(tables_to_migrate):
                    await postgres_conn.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')

            await postgres_conn.execute(CREATE_TABLES_SQL)

            print(f"[INFO] Starting migration from {sqlite_path} to PostgreSQL")
            for table in tables_to_migrate:
                count = await migrate_table(postgres_conn, sqlite_conn, table)
                print(f"[OK] {table}: {count} rows copied")

            print("[OK] Migration finished successfully.")
        finally:
            await postgres_conn.close()
    finally:
        sqlite_conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate bot.sqlite3 to PostgreSQL.")
    parser.add_argument(
        "--sqlite",
        default=str(ROOT_DIR / "database" / "bot.sqlite3"),
        help="Path to the SQLite DB file (default: dev/database/bot.sqlite3)",
    )
    parser.add_argument(
        "--postgres-dsn",
        default=None,
        help="PostgreSQL DSN, for example: postgresql://user:password@localhost:5432/reolo_bot",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing PostgreSQL tables before loading data",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    dsn = resolve_postgres_dsn(args.postgres_dsn)
    asyncio.run(migrate(args.sqlite, dsn, reset=args.reset))
