from __future__ import annotations

from .connection import execute, fetch, fetchrow


async def init_db(additional_command: str = "") -> None:
    """Создает необходимые таблицы PostgreSQL, если их еще нет."""
    await execute(
        f"""
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
            achievement_id INTEGER NOT NULL REFERENCES achievements(id),
            obtained_at BIGINT,
            PRIMARY KEY (user_id, achievement_id)
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

        {additional_command}
        """
    )


def _normalize_user_id(user_id: int | str) -> int | None:
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


async def user_exists(user_id: int | str) -> bool:
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return False
    row = await fetchrow("SELECT 1 FROM user_accounts WHERE user_id = $1", normalized_id)
    return row is not None


async def get_user(user_id: int | str) -> dict | None:
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return None
    row = await fetchrow("SELECT * FROM user_accounts WHERE user_id = $1", normalized_id)
    return dict(row) if row else None


async def create_user_if_missing(user_id: int | str, first_name: str | None, last_name: str | None) -> None:
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return
    await execute(
        """
        INSERT INTO user_accounts(user_id, first_name, last_name, balance)
        VALUES ($1, $2, $3, 0)
        ON CONFLICT (user_id) DO NOTHING
        """,
        normalized_id,
        first_name,
        last_name,
    )


async def get_all_users() -> list[dict]:
    rows = await fetch("SELECT * FROM user_accounts")
    return [dict(row) for row in rows]


async def get_post_counter(user_id: int | str) -> int:
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return 0
    row = await fetchrow("SELECT post_counter FROM user_accounts WHERE user_id = $1", normalized_id)
    return row["post_counter"] if row else 0


async def add_to_post_counter(user_id: int | str, count: int = 1) -> None:
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return
    await execute(
        "UPDATE user_accounts SET post_counter = post_counter + $1 WHERE user_id = $2",
        count,
        normalized_id,
    )


async def get_rpg_player(user_id: int) -> dict | None:
    row = await fetchrow("SELECT * FROM rpg_players WHERE user_id = $1", user_id)
    if row is None:
        return None
    data = dict(row)
    data["inventory"] = data.pop("inventory_json")
    data["id"] = data.pop("user_id")
    return data


async def upsert_rpg_player(player_data: dict) -> None:
    inventory_json = player_data.get("inventory", [])
    await execute(
        """
        INSERT INTO rpg_players(user_id, cls, race, hp, level, atk, defn, dodge, inventory_json)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
        ON CONFLICT(user_id) DO UPDATE SET
            cls = EXCLUDED.cls,
            race = EXCLUDED.race,
            hp = EXCLUDED.hp,
            level = EXCLUDED.level,
            atk = EXCLUDED.atk,
            defn = EXCLUDED.defn,
            dodge = EXCLUDED.dodge,
            inventory_json = EXCLUDED.inventory_json
        """,
        player_data["id"],
        player_data["cls"],
        player_data["race"],
        player_data["hp"],
        player_data["level"],
        player_data["atk"],
        player_data["defn"],
        player_data["dodge"],
        inventory_json,
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
