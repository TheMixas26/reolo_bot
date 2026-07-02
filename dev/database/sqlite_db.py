import json
from .connection import _conn, _DB_LOCK, _get_connection, DB_PATH

def init_db(additional_command = "") -> None:
    """Создает необходимые таблицы, если их еще нет"""
    with _DB_LOCK:
        _conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                balance REAL NOT NULL DEFAULT 0,
                post_counter INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS birthdays (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                username TEXT,
                day INTEGER NOT NULL,
                month INTEGER NOT NULL,
                year INTEGER NOT NULL,
                personal_notify INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS rpg_players (
                user_id INTEGER PRIMARY KEY,
                cls TEXT NOT NULL,
                race TEXT NOT NULL,
                hp INTEGER NOT NULL,
                level INTEGER NOT NULL,
                atk INTEGER NOT NULL,
                defn INTEGER NOT NULL,
                dodge REAL NOT NULL,
                inventory_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                conditions TEXT
            );

            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER NOT NULL,
                achievement_id INTEGER NOT NULL,
                obtained_at INTEGER,
                PRIMARY KEY (user_id, achievement_id),
                FOREIGN KEY (achievement_id) REFERENCES achievements(id)
            );

            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rarity TEXT NOT NULL,
                hp INTEGER NOT NULL,
                atk INTEGER NOT NULL,
                def INTEGER NOT NULL,
                type TEXT,
                category TEXT,
                ability TEXT,
                image TEXT,
                desc TEXT
            );

            CREATE TABLE IF NOT EXISTS card_packs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                amount INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, card_id)
            );

            CREATE TABLE IF NOT EXISTS card_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                reward INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                closed_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS card_event_rewards (
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rewarded_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (event_id, user_id)
            );

            {additional_command}
            """
        )

        _conn.commit()


# ---- user_accounts ----
def _normalize_user_id(user_id: int | str) -> int | None:
    """Пытается привести user_id к целому числу. Если не получается, возвращает None"""
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def user_exists(user_id: int | str) -> bool:
    """Проверяет, существует ли пользователь с данным user_id в базе данных"""
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return False

    with _DB_LOCK:
        row = _conn.execute("SELECT 1 FROM user_accounts WHERE user_id = ?", (normalized_id,)).fetchone()
    return row is not None


def get_user(user_id: int | str) -> dict | None:
    """Возвращает данные пользователя с данным user_id в виде словаря. Если пользователь не найден или user_id невалидный, возвращает None"""
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return None

    with _DB_LOCK:
        row = _conn.execute("SELECT * FROM user_accounts WHERE user_id = ?", (normalized_id,)).fetchone()
    return dict(row) if row else None


def create_user_if_missing(user_id: int | str, first_name: str | None, last_name: str | None) -> None:
    """Создает запись о пользователе в базе данных, если ее еще нет. Игнорирует попытки создать запись с невалидным user_id"""
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return

    with _DB_LOCK:
        _conn.execute(
            """
            INSERT OR IGNORE INTO user_accounts(user_id, first_name, last_name, balance)
            VALUES (?, ?, ?, 0)
            """,
            (normalized_id, first_name, last_name),
        )
        _conn.commit()

def get_all_users() -> list[dict]:
    """Возвращает список всех пользователей с их данными"""
    with _DB_LOCK:
        rows = _conn.execute("SELECT * FROM user_accounts").fetchall()
    return [dict(row) for row in rows]

def get_post_counter(user_id: int | str) -> int:
    """Возвращает количество постов пользователя. Если пользователь не найден или user_id невалидный, возвращает 0"""
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return 0

    with _DB_LOCK:
        row = _conn.execute("SELECT post_counter FROM user_accounts WHERE user_id = ?", (normalized_id,)).fetchone()
    return row["post_counter"] if row else 0


def add_to_post_counter(user_id: int | str, count: int = 1) -> None:
    """Увеличивает счетчик постов пользователя на заданное количество. Если пользователь не найден или user_id невалидный, ничего не делает"""
    old_value = get_post_counter(user_id)
    new_value = old_value + count

    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return

    with _DB_LOCK:
        _conn.execute("UPDATE user_accounts SET post_counter = ? WHERE user_id = ?", (new_value, normalized_id))
        _conn.commit()

# ---- rpg_players ----
def get_rpg_player(user_id: int) -> dict | None:
    """Возвращает запись о RPG-персонаже пользователя с его данными"""   
    with _DB_LOCK:
        row = _conn.execute("SELECT * FROM rpg_players WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["inventory"] = json.loads(data.pop("inventory_json"))
    data["id"] = data.pop("user_id")
    return data


def upsert_rpg_player(player_data: dict) -> None:
    """Создает или обновляет запись о RPG-персонаже пользователя."""
    inventory_json = json.dumps(player_data.get("inventory", []), ensure_ascii=False)
    with _DB_LOCK:
        _conn.execute(
            """
            INSERT INTO rpg_players(user_id, cls, race, hp, level, atk, defn, dodge, inventory_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                cls = excluded.cls,
                race = excluded.race,
                hp = excluded.hp,
                level = excluded.level,
                atk = excluded.atk,
                defn = excluded.defn,
                dodge = excluded.dodge,
                inventory_json = excluded.inventory_json
            """,
            (
                player_data["id"],
                player_data["cls"],
                player_data["race"],
                player_data["hp"],
                player_data["level"],
                player_data["atk"],
                player_data["defn"],
                player_data["dodge"],
                inventory_json,
            ),
        )
        _conn.commit()


# -=-=-=-=-=-=- Achievements -=-=-=-=-=-=-



# -=-=-=-=-=-=- Cards & Inventory -=-=-=-=-=-=-



# ----- Функции для работы с картами -----



init_db()

if __name__ == "__main__":
    init_db()
