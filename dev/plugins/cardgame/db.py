from database.connection import _conn, _DB_LOCK
from .catalog import sort_cards, get_rarity_label, CARD_DEFINITIONS, PACK_DEFINITIONS

def get_all_cards():
    """Возвращает список всех карт."""
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute("SELECT * FROM cards ORDER BY id")
        return sort_cards([dict(row) for row in cur.fetchall()])

def get_card_by_id(card_id: int):
    """Возвращает карту по id."""
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def get_cards_by_rarity(rarity: str):
    """Возвращает карты заданной редкости."""
    with _DB_LOCK:
        cur = _conn.cursor()
        rarity_label = get_rarity_label(rarity)
        cur.execute(
            """
            SELECT * FROM cards
            WHERE rarity = ? OR rarity = ? OR rarity LIKE ?
            """,
            (rarity, rarity_label, f"%-{rarity_label}"),
        )
        return sort_cards([dict(row) for row in cur.fetchall()])


def get_cards_by_category(category: str):
    """Возвращает карты из указанного пака/категории."""
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute("SELECT * FROM cards WHERE category = ? ORDER BY id", (category,))
        return sort_cards([dict(row) for row in cur.fetchall()])


def get_pack_names() -> list[str]:
    """Возвращает список всех доступных паков."""
    return [pack["name"] for pack in get_all_packs(active_only=True)]


def get_all_packs(active_only: bool = False) -> list[dict]:
    """Возвращает список всех паков."""
    with _DB_LOCK:
        cur = _conn.cursor()
        if active_only:
            cur.execute("SELECT * FROM card_packs WHERE is_active = 1 ORDER BY price, name")
        else:
            cur.execute("SELECT * FROM card_packs ORDER BY is_active DESC, price, name")
        return [dict(row) for row in cur.fetchall()]


def get_pack_by_id(pack_id: int) -> dict | None:
    with _DB_LOCK:
        row = _conn.execute("SELECT * FROM card_packs WHERE id = ?", (pack_id,)).fetchone()
        return dict(row) if row else None


def get_pack_by_name(pack_name: str) -> dict | None:
    with _DB_LOCK:
        row = _conn.execute("SELECT * FROM card_packs WHERE name = ?", (pack_name,)).fetchone()
        return dict(row) if row else None


def upsert_pack(name: str, price: int, description: str | None = None, is_active: bool = True) -> None:
    with _DB_LOCK:
        _conn.execute(
            """
            INSERT INTO card_packs(name, price, description, is_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                price = excluded.price,
                description = excluded.description,
                is_active = excluded.is_active
            """,
            (name, price, description, 1 if is_active else 0),
        )
        _conn.commit()


def update_pack(pack_id: int, *, name: str | None = None, price: int | None = None, description: str | None = None, is_active: bool | None = None) -> None:
    pack = get_pack_by_id(pack_id)
    if pack is None:
        raise ValueError("Пак не найден.")

    new_name = name if name is not None else pack["name"]
    new_price = price if price is not None else pack["price"]
    new_description = description if description is not None else pack["description"]
    new_active = (1 if is_active else 0) if is_active is not None else pack["is_active"]

    with _DB_LOCK:
        _conn.execute(
            """
            UPDATE card_packs
            SET name = ?, price = ?, description = ?, is_active = ?
            WHERE id = ?
            """,
            (new_name, new_price, new_description, new_active, pack_id),
        )
        if new_name != pack["name"]:
            _conn.execute("UPDATE cards SET category = ? WHERE category = ?", (new_name, pack["name"]))
        _conn.commit()

def add_to_inventory(user_id: int, card_id: int, amount: int = 1) -> None:
    """Добавляет карту в инвентарь пользователя."""
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute("""
            INSERT INTO inventory (user_id, card_id, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, card_id) DO UPDATE SET amount = amount + excluded.amount
        """, (user_id, card_id, amount))
        _conn.commit()

def get_inventory(user_id: int):
    """Возвращает инвентарь пользователя с данными карт."""
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute("""
            SELECT c.*, i.amount
            FROM inventory i
            JOIN cards c ON i.card_id = c.id
            WHERE i.user_id = ?
        """, (user_id,))
        return sort_cards([dict(row) for row in cur.fetchall()])


def add_card(card_data: dict) -> int:
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute(
            """
            INSERT INTO cards (name, rarity, hp, atk, def, type, category, ability, image, desc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
            ),
        )
        _conn.commit()
        return int(cur.lastrowid)


def update_card(card_id: int, card_data: dict) -> None:
    card = get_card_by_id(card_id)
    if card is None:
        raise ValueError("Карта не найдена.")

    merged = {**card, **card_data}
    with _DB_LOCK:
        _conn.execute(
            """
            UPDATE cards
            SET name = ?, rarity = ?, hp = ?, atk = ?, def = ?, type = ?, category = ?, ability = ?, image = ?, desc = ?
            WHERE id = ?
            """,
            (
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
            ),
        )
        _conn.commit()


def create_card_event(title: str, reward: int, description: str | None = None) -> int:
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute(
            """
            INSERT INTO card_events(title, description, reward, status)
            VALUES (?, ?, ?, 'active')
            """,
            (title, description, reward),
        )
        _conn.commit()
        return int(cur.lastrowid)


def get_card_event(event_id: int) -> dict | None:
    with _DB_LOCK:
        row = _conn.execute("SELECT * FROM card_events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def get_card_events(status: str | None = None) -> list[dict]:
    with _DB_LOCK:
        cur = _conn.cursor()
        if status is None:
            cur.execute("SELECT * FROM card_events ORDER BY status = 'active' DESC, id DESC")
        else:
            cur.execute("SELECT * FROM card_events WHERE status = ? ORDER BY id DESC", (status,))
        return [dict(row) for row in cur.fetchall()]


def close_card_event(event_id: int) -> None:
    with _DB_LOCK:
        _conn.execute(
            """
            UPDATE card_events
            SET status = 'closed', closed_at = strftime('%s', 'now')
            WHERE id = ?
            """,
            (event_id,),
        )
        _conn.commit()


def reward_card_event_participant(event_id: int, user_id: int) -> tuple[bool, int]:
    from plugins.bank.db import get_balance
    
    event = get_card_event(event_id)
    if event is None:
        raise ValueError("Ивент не найден.")
    if event["status"] != "active":
        raise ValueError("Ивент уже закрыт.")

    with _DB_LOCK:
        existing = _conn.execute(
            "SELECT 1 FROM card_event_rewards WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        ).fetchone()
        if existing is not None:
            return False, int(event["reward"])

        current_balance = get_balance(user_id)
        _conn.execute(
            "INSERT INTO card_event_rewards(event_id, user_id) VALUES (?, ?)",
            (event_id, user_id),
        )
        _conn.execute(
            "UPDATE user_accounts SET balance = ? WHERE user_id = ?",
            (current_balance + event["reward"], user_id),
        )
        _conn.commit()
        return True, int(event["reward"])

def _seed_cards_if_empty() -> None:
    cur = _conn.cursor()
    cur.executemany(
        """
        INSERT OR IGNORE INTO cards (id, name, rarity, hp, atk, def, type, category, ability, image, desc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        CARD_DEFINITIONS,
    )
    _conn.commit()


def _seed_packs_if_empty() -> None:
    cur = _conn.cursor()
    cur.executemany(
        """
        INSERT OR IGNORE INTO card_packs (name, price, description, is_active)
        VALUES (?, ?, ?, 1)
        """,
        PACK_DEFINITIONS,
    )
    _conn.commit()


def init_cardgame_database():
    with _DB_LOCK:
        _seed_cards_if_empty()
        _seed_packs_if_empty()
        
        _conn.commit()

