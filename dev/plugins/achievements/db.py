from database.connection import _conn, _DB_LOCK

def get_all_achievements() -> list[dict]:
    """Возвращает список всех достижений с их данными (code, name, description)"""
    with _DB_LOCK:
        rows = _conn.execute("SELECT code, name, description FROM achievements").fetchall()
    return [dict(row) for row in rows]


def get_achievement_by_code(code: str) -> dict | None:
    """Возвращает одно достижение по уникальному коду или None."""
    with _DB_LOCK:
        row = _conn.execute(
            "SELECT id, code, name, description FROM achievements WHERE code = ?",
            (code,),
        ).fetchone()
    return dict(row) if row else None


def get_achievements_by_code(code: str) -> list[dict]:
    """Совместимость со старым API: возвращает список из одного достижения либо пустой список."""
    achievement = get_achievement_by_code(code)
    return [achievement] if achievement else []

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
    with _DB_LOCK:
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
