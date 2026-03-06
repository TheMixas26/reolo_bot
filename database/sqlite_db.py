import json
import sqlite3
from pathlib import Path
from threading import Lock

DB_PATH = Path("database/bot.sqlite3")
_DB_LOCK = Lock()


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = _get_connection()


def init_db() -> None:
    with _DB_LOCK:
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                balance REAL NOT NULL DEFAULT 0
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
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id INTEGER NOT NULL,
                achievement_id INTEGER NOT NULL,
                obtained_at INTEGER,
                PRIMARY KEY (user_id, achievement_id),
                FOREIGN KEY (achievement_id) REFERENCES achievements(id)
            );
            """
        )
        _conn.commit()


# ---- user_accounts ----
def _normalize_user_id(user_id) -> int | None:
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def user_exists(user_id: int | str) -> bool:
    normalized_id = _normalize_user_id(user_id)
    if normalized_id is None:
        return False

    row = _conn.execute("SELECT 1 FROM user_accounts WHERE user_id = ?", (normalized_id,)).fetchone()
    return row is not None


def create_user_if_missing(user_id: int | str, first_name: str | None, last_name: str | None) -> None:
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
    rows = _conn.execute("SELECT user_id, first_name, last_name, balance FROM user_accounts").fetchall()
    return [dict(row) for row in rows]


def get_balance(user_id: int) -> float:
    row = _conn.execute("SELECT balance FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return 0
    return row["balance"]


def set_balance(user_id: int, balance: float) -> None:
    with _DB_LOCK:
        _conn.execute("UPDATE user_accounts SET balance = ? WHERE user_id = ?", (balance, user_id))
        _conn.commit()


# ---- birthdays ----
def upsert_birthday(user_id: int, name: str, day: int, month: int, year: int, username: str | None = None) -> None:
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
    rows = _conn.execute("SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays").fetchall()
    return [dict(row) for row in rows]


def update_birthday_name(user_id: int, name: str) -> None:
    with _DB_LOCK:
        _conn.execute("UPDATE birthdays SET name = ? WHERE user_id = ?", (name, user_id))
        _conn.commit()


def get_birthday(user_id: int) -> dict | None:
    row = _conn.execute(
        "SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def set_personal_notify(user_id: int, enabled: bool) -> None:
    with _DB_LOCK:
        _conn.execute("UPDATE birthdays SET personal_notify = ? WHERE user_id = ?", (1 if enabled else 0, user_id))
        _conn.commit()


# ---- rpg_players ----
def get_rpg_player(user_id: int) -> dict | None:
    row = _conn.execute("SELECT * FROM rpg_players WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["inventory"] = json.loads(data.pop("inventory_json"))
    data["id"] = data.pop("user_id")
    return data


def upsert_rpg_player(player_data: dict) -> None:
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



def achievements_list(code: str) -> list[dict]:
    rows = _conn.execute("SELECT id, code, name, description FROM achievements WHERE code = ?", (code,)).fetchall()
    return [dict(row) for row in rows]


def add_achievement(code: str, name: str, description: str) -> None:
    with _DB_LOCK:
        _conn.execute(
            "INSERT OR IGNORE INTO achievements(code, name, description) VALUES (?, ?, ?)",
            (code, name, description),
        )
        _conn.commit()


def grant_achievement(user_id: int, achievement_code: str) -> None:
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




init_db()
