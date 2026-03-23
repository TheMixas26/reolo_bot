import json
import sqlite3
from pathlib import Path
from threading import Lock

DB_PATH = Path("database/bot.sqlite3")
_DB_LOCK = Lock()


# TODO: В отдельный игро-конфиг
rarity_weights = {
    "C": 60,
    "UC": 25,
    "R": 10,
    "SR": 4,
    "UR": 1,
    "L": 0.1
}

def _get_connection() -> sqlite3.Connection:
    """Создает папку для базы данных, если ее нет, и возвращает соединение с базой данных"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = _get_connection()


def _seed_cards_if_empty() -> None:
    cur = _conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cards")
    if cur.fetchone()[0] != 0:
        return

    cards_data = [
        (1, "Дуэлянт", "R", 200, 200, 150, "MORTAL", "Верные подписчики", None, None, "Самая популярная карта в дуэлях! Эта подписчица стабильно радует нас экзистенциальными вопросами о мироздании."),
        (2, "Сонный балбес", "R", 200, 100, 300, "MORTAL", "Верные подписчики", None, None, "Серый Кардинал Имперского Вестника. Всегда читает посты, всегда смотрит комментарии. Всегда рядом)"),
        (3, "Татьяна", "R", 600, 100, 350, "MORTAL", "Верные подписчики", None, None, None),
        (4, "Варя (Предложка)", "UR", 1000, 1000, 1111, "MORTAL", "Админы всея канала", None, None, "Именно она заботливо передаёт ваши посты администрации канала."),
        (5, "Just_Nika", "UR", 1250, 1250, 900, "MORTAL", "Админы всея канала", None, None, None),
        (6, "Улитка на склоне", "UR", 500, 500, 2500, "MORTAL", "Админы всея канала", None, None, None),
        (7, "Амодерни Боровски", "UR", 1200, 1200, 1000, "COUNCIL", "Админы всея канала", None, None, None),
        (8, "Амодерни Боровски", "L", 3000, 3000, 2500, "COUNCIL", "Высший Совет", None, None, None),
        (9, "Генрих Многорукий", "L", 5000, 5000, 1000, "COUNCIL", "Высший Совет", None, None, None),
        (10, "Фелония Ламберт", "L", 2500, 2500, 3000, "COUNCIL", "Высший Совет", None, None, None),
        (11, "ПАША", "SP", 700, 700, 800, "MORTAL", "Голосование за имя Предложки", None, None, "Публичное Агенство Шумных Анонсов - именно так могли звать Предложку."),
    ]
    cur.executemany(
        """
        INSERT INTO cards (id, name, rarity, hp, atk, def, type, category, ability, image, desc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        cards_data,
    )
    _conn.commit()


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

            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                amount INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, card_id)
            );

            {additional_command}
            """
        )
        _seed_cards_if_empty()

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

    row = _conn.execute("SELECT 1 FROM user_accounts WHERE user_id = ?", (normalized_id,)).fetchone()
    return row is not None


def get_user(user_id: int | str) -> dict | None:
    """Возвращает данные пользователя с данным user_id в виде словаря. Если пользователь не найден или user_id невалидный, возвращает None"""
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return None

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
    rows = _conn.execute("SELECT * FROM user_accounts").fetchall()
    return [dict(row) for row in rows]

def get_post_counter(user_id: int | str) -> int:
    """Возвращает количество постов пользователя. Если пользователь не найден или user_id невалидный, возвращает 0"""
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return 0

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


def get_balance(user_id: int) -> float:
    """Возвращает баланс пользователя. Если пользователь не найден, возвращает 0"""
    row = _conn.execute("SELECT balance FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return 0
    return row["balance"]


def set_balance(user_id: int, balance: float) -> None:
    """Устанавливает баланс пользователя. Если пользователь не найден... ничего не делает"""
    with _DB_LOCK:
        _conn.execute("UPDATE user_accounts SET balance = ? WHERE user_id = ?", (balance, user_id))
        _conn.commit()


# ---- birthdays ----
def upsert_birthday(user_id: int, name: str, day: int, month: int, year: int, username: str | None = None) -> None:
    """Создает или обновляет запись о дне рождения пользователя. Если username не передан, сохраняет существующий username (если он есть)"""
    with _DB_LOCK:
        _conn.execute(
            """
            INSERT INTO birthdays(user_id, name, username, day, month, year)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                username = COALESCE(excluded.username, birthdays.username),
                day = excluded.day,
                month = excluded.month,
                year = excluded.year
            """,
            (user_id, name, username, day, month, year),
        )
        _conn.commit()


def get_all_birthdays() -> list[dict]:
    """Возвращает список всех записей о днях рождения пользователей с их данными (user_id, name, username, day, month, year, personal_notify)"""
    rows = _conn.execute("SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays").fetchall()
    return [dict(row) for row in rows]


def update_birthday_name(user_id: int, name: str) -> None:
    """Обновляет имя, связанное с днем рождения пользователя. Если пользователь не найден... ничего не делает"""
    with _DB_LOCK:
        _conn.execute("UPDATE birthdays SET name = ? WHERE user_id = ?", (name, user_id))
        _conn.commit()


def get_birthday(user_id: int) -> dict | None:
    """Возвращает запись о дне рождения пользователя с его данными (user_id, name, username, day, month, year, personal_notify). Если пользователь не найден, возвращает None"""
    row = _conn.execute(
        "SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def set_personal_notify(user_id: int, enabled: bool) -> None:
    """Включает или отключает персональные уведомления о дне рождения для пользователя. Если пользователь не найден... ничего не делает"""
    with _DB_LOCK:
        _conn.execute("UPDATE birthdays SET personal_notify = ? WHERE user_id = ?", (1 if enabled else 0, user_id))
        _conn.commit()


# ---- rpg_players ----
def get_rpg_player(user_id: int) -> dict | None:
    """Возвращает запись о RPG-персонаже пользователя с его данными"""   
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

def get_all_achievements() -> list[dict]:
    """Возвращает список всех достижений с их данными (code, name, description)"""
    rows = _conn.execute("SELECT code, name, description FROM achievements").fetchall()
    return [dict(row) for row in rows]


# !!! Какого лешего эта функция делает??? У нас же код должен быть уникальным, зачем возвращать список??? 
# TODO: Починить архитектуру ачивок
def get_achievements_by_code(code: str) -> list[dict]:
    """Возвращает список достижений, соответствующих заданному коду. Если достижений с таким кодом нет, возвращает пустой список"""
    rows = _conn.execute("SELECT id, code, name, description FROM achievements WHERE code = ?", (code,)).fetchall()
    return [dict(row) for row in rows]

def add_achievement(code: str, name: str, description: str) -> None:
    """Создает новое достижение с заданным кодом, именем и описанием. Если достижение с таким кодом уже существует... ничего не делает"""
    with _DB_LOCK:
        _conn.execute(
            "INSERT OR IGNORE INTO achievements(code, name, description) VALUES (?, ?, ?)",
            (code, name, description),
        )
        _conn.commit()

def update_achievement(achievement_code: str, name: str | None = None, description: str | None = None, conditions: str | None = None) -> None:
    """Обновляет параметры достижения. Если достижение не найдено, выбрасывает исключение ValueError"""
    with _DB_LOCK:
        achievement = _conn.execute("SELECT id FROM achievements WHERE code = ?", (achievement_code,)).fetchone()
        if achievement is None:
            raise ValueError(f"Achievement with code '{achievement_code}' does not exist.")
        if name is not None:
            _conn.execute("UPDATE achievements SET name = ? WHERE code = ?", (name, achievement_code))
        if description is not None:
            _conn.execute("UPDATE achievements SET description = ? WHERE code = ?", (description, achievement_code))
        if conditions is not None:
            _conn.execute("UPDATE achievements SET conditions = ? WHERE code = ?", (conditions, achievement_code))
        _conn.commit()

def grant_achievement(user_id: int, achievement_code: str) -> None:
    """Выдает достижение пользователю. Если пользователь уже получил это достижение, ничего не делает. Если достижения с таким кодом не существует, выбрасывает исключение ValueError"""
    with _DB_LOCK:
        achievement = _conn.execute("SELECT id FROM achievements WHERE code = ?", (achievement_code,)).fetchone()
        if achievement is None:
            raise ValueError(f"Achievement with code '{achievement_code}' does not exist.")
        achievement_id = achievement["id"]
        _conn.execute(
            "INSERT OR IGNORE INTO user_achievements(user_id, achievement_id, obtained_at) VALUES (?, ?, strftime('%s', 'now'))",
            (user_id, achievement_id),
        )
        _conn.commit()


def revoke_achievement(user_id: int, achievement_code: str) -> None:
    """Отзывает достижение у пользователя. Если пользователь не имеет этого достижения, ничего не делает. Если достижения с таким кодом не существует, выбрасывает исключение ValueError"""
    with _DB_LOCK:
        achievement = _conn.execute("SELECT id FROM achievements WHERE code = ?", (achievement_code,)).fetchone()
        if achievement is None:
            raise ValueError(f"Achievement with code '{achievement_code}' does not exist.")
        achievement_id = achievement["id"]
        _conn.execute(
            "DELETE FROM user_achievements WHERE user_id = ? AND achievement_id = ?",
            (user_id, achievement_id),
        )
        _conn.commit()

def get_user_achievements(user_id: int) -> list[dict]:
    """Возвращает список достижений пользователя с их данными (code, name, description, obtained_at). Если пользователь не имеет достижений, возвращает пустой список"""                      
    rows = _conn.execute(
        """
        SELECT a.code, a.name, a.description, ua.obtained_at
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = ?
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]

# -=-=-=-=-=-=- Cards & Inventory -=-=-=-=-=-=-



# ----- Функции для работы с картами -----
def get_all_cards():
    """Возвращает список всех карт."""
    with _DB_LOCK:
        cur = _conn.cursor()
        cur.execute("SELECT * FROM cards ORDER BY id")
        return [dict(row) for row in cur.fetchall()]

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
        cur.execute("SELECT * FROM cards WHERE rarity = ?", (rarity,))
        return [dict(row) for row in cur.fetchall()]



# ----- Инвентарь -----
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
        return [dict(row) for row in cur.fetchall()]

def roll_card(user_id: int):
    """Случайная карта по редкости, добавляет в инвентарь."""
    import random
    rarities = list(rarity_weights.keys())
    weights = list(rarity_weights.values())
    rarity = random.choices(rarities, weights=weights, k=1)[0]

    cards = get_cards_by_rarity(rarity)
    if not cards:
        cards = get_all_cards()
    card = random.choice(cards)

    add_to_inventory(user_id, card["id"])
    return card



init_db()

if __name__ == "__main__":
    init_db()
