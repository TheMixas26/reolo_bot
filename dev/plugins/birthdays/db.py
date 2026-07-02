from database.connection import _conn, _DB_LOCK


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
    with _DB_LOCK:
        rows = _conn.execute("SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays").fetchall()
    return [dict(row) for row in rows]


def update_birthday_name(user_id: int, name: str) -> None:
    """Обновляет имя, связанное с днем рождения пользователя. Если пользователь не найден... ничего не делает"""
    with _DB_LOCK:
        _conn.execute("UPDATE birthdays SET name = ? WHERE user_id = ?", (name, user_id))
        _conn.commit()


def get_birthday(user_id: int) -> dict | None:
    """Возвращает запись о дне рождения пользователя с его данными (user_id, name, username, day, month, year, personal_notify). Если пользователь не найден, возвращает None"""
    with _DB_LOCK:
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
