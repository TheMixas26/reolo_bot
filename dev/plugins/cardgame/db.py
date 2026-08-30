from database.connection import execute, fetch, fetchrow, fetchval, get_pool
from .catalog import sort_cards, get_rarity_label, CARD_DEFINITIONS, PACK_DEFINITIONS


async def get_all_cards():
    rows = await fetch('SELECT * FROM cards ORDER BY id')
    return sort_cards([dict(row) for row in rows])


async def get_card_by_id(card_id: int):
    row = await fetchrow("SELECT * FROM cards WHERE id = $1", card_id)
    return dict(row) if row else None


async def get_cards_by_rarity(rarity: str):
    rarity_label = get_rarity_label(rarity)
    rows = await fetch(
        """
        SELECT * FROM cards
        WHERE rarity = $1 OR rarity = $2 OR rarity LIKE $3
        """,
        rarity,
        rarity_label,
        f"%-{rarity_label}",
    )
    return sort_cards([dict(row) for row in rows])


async def get_cards_by_category(category: str):
    rows = await fetch("SELECT * FROM cards WHERE category = $1 ORDER BY id", category)
    return sort_cards([dict(row) for row in rows])


async def get_pack_names() -> list[str]:
    return [pack["name"] for pack in await get_all_packs(active_only=True)]


async def get_all_packs(active_only: bool = False) -> list[dict]:
    if active_only:
        rows = await fetch("SELECT * FROM card_packs WHERE is_active = TRUE ORDER BY price, name")
    else:
        rows = await fetch("SELECT * FROM card_packs ORDER BY is_active DESC, price, name")
    return [dict(row) for row in rows]


async def get_pack_by_id(pack_id: int) -> dict | None:
    row = await fetchrow("SELECT * FROM card_packs WHERE id = $1", pack_id)
    return dict(row) if row else None


async def get_pack_by_name(pack_name: str) -> dict | None:
    row = await fetchrow("SELECT * FROM card_packs WHERE name = $1", pack_name)
    return dict(row) if row else None


async def upsert_pack(name: str, price: int, description: str | None = None, is_active: bool = True) -> None:
    await execute(
        """
        INSERT INTO card_packs(name, price, description, is_active)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT(name) DO UPDATE SET
            price = EXCLUDED.price,
            description = EXCLUDED.description,
            is_active = EXCLUDED.is_active
        """,
        name,
        price,
        description,
        is_active,
    )


async def update_pack(pack_id: int, *, name: str | None = None, price: int | None = None, description: str | None = None, is_active: bool | None = None) -> None:
    pack = await get_pack_by_id(pack_id)
    if pack is None:
        raise ValueError("Пак не найден.")

    new_name = name if name is not None else pack["name"]
    new_price = price if price is not None else pack["price"]
    new_description = description if description is not None else pack["description"]
    new_active = is_active if is_active is not None else pack["is_active"]

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE card_packs
                SET name = $1, price = $2, description = $3, is_active = $4
                WHERE id = $5
                """,
                new_name,
                new_price,
                new_description,
                new_active,
                pack_id,
            )
            if new_name != pack["name"]:
                await conn.execute("UPDATE cards SET category = $1 WHERE category = $2", new_name, pack["name"])


async def add_to_inventory(user_id: int, card_id: int, amount: int = 1) -> None:
    await execute(
        """
        INSERT INTO inventory (user_id, card_id, amount)
        VALUES ($1, $2, $3)
        ON CONFLICT(user_id, card_id) DO UPDATE SET amount = inventory.amount + EXCLUDED.amount
        """,
        user_id,
        card_id,
        amount,
    )


async def get_inventory(user_id: int):
    rows = await fetch(
        """
        SELECT c.*, i.amount
        FROM inventory i
        JOIN cards c ON i.card_id = c.id
        WHERE i.user_id = $1
        """,
        user_id,
    )
    return sort_cards([dict(row) for row in rows])


async def add_card(card_data: dict) -> int:
    return await fetchval(
        """
        INSERT INTO cards (name, rarity, hp, atk, def, type, category, ability, image, "desc")
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """,
        card_data["name"],
        card_data["rarity"],
        card_data["hp"],
        card_data["atk"],
        card_data["def"],
        card_data.get("type"),
        card_data.get("category"),
        card_data.get("ability"),
        card_data.get("image"),
        card_data.get("desc"),
    )


async def update_card(card_id: int, card_data: dict) -> None:
    card = await get_card_by_id(card_id)
    if card is None:
        raise ValueError("Карта не найдена.")

    merged = {**card, **card_data}
    await execute(
        """
        UPDATE cards
        SET name = $1, rarity = $2, hp = $3, atk = $4, def = $5,
            type = $6, category = $7, ability = $8, image = $9, "desc" = $10
        WHERE id = $11
        """,
        merged["name"],
        merged["rarity"],
        merged["hp"],
        merged["atk"],
        merged["def"],
        merged.get("type"),
        merged.get("category"),
        merged.get("ability"),
        merged.get("image"),
        merged.get("desc"),
        card_id,
    )


async def create_card_event(title: str, reward: int, description: str | None = None) -> int:
    return await fetchval(
        """
        INSERT INTO card_events(title, description, reward, status)
        VALUES ($1, $2, $3, 'active')
        RETURNING id
        """,
        title,
        description,
        reward,
    )


async def get_card_event(event_id: int) -> dict | None:
    row = await fetchrow("SELECT * FROM card_events WHERE id = $1", event_id)
    return dict(row) if row else None


async def get_card_events(status: str | None = None) -> list[dict]:
    if status is None:
        rows = await fetch("SELECT * FROM card_events ORDER BY (status = 'active') DESC, id DESC")
    else:
        rows = await fetch("SELECT * FROM card_events WHERE status = $1 ORDER BY id DESC", status)
    return [dict(row) for row in rows]


async def close_card_event(event_id: int) -> None:
    await execute(
        """
        UPDATE card_events
        SET status = 'closed', closed_at = EXTRACT(EPOCH FROM NOW())::BIGINT
        WHERE id = $1
        """,
        event_id,
    )


async def reward_card_event_participant(event_id: int, user_id: int) -> tuple[bool, int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            event = await conn.fetchrow("SELECT * FROM card_events WHERE id = $1", event_id)
            if event is None:
                raise ValueError("Ивент не найден.")
            if event["status"] != "active":
                raise ValueError("Ивент уже закрыт.")

            existing = await conn.fetchrow(
                "SELECT 1 FROM card_event_rewards WHERE event_id = $1 AND user_id = $2",
                event_id,
                user_id,
            )
            if existing is not None:
                return False, int(event["reward"])

            await conn.execute(
                "INSERT INTO card_event_rewards(event_id, user_id) VALUES ($1, $2)",
                event_id,
                user_id,
            )
            await conn.execute(
                "UPDATE user_accounts SET balance = balance + $1 WHERE user_id = $2",
                event["reward"],
                user_id,
            )
            return True, int(event["reward"])


async def _seed_cards_if_empty() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO cards (id, name, rarity, hp, atk, def, type, category, ability, image, "desc")
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT(id) DO NOTHING
            """,
            CARD_DEFINITIONS,
        )
        await conn.execute(
            "SELECT setval(pg_get_serial_sequence('cards', 'id'), COALESCE((SELECT MAX(id) FROM cards), 1), TRUE)"
        )


async def _seed_packs_if_empty() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO card_packs (name, price, description, is_active)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT(name) DO NOTHING
            """,
            PACK_DEFINITIONS,
        )


async def init_cardgame_database():
    await _seed_cards_if_empty()
    await _seed_packs_if_empty()
