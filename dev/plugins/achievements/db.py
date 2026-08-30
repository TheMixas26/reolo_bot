from database.connection import execute, fetch, fetchrow


async def get_all_achievements() -> list[dict]:
    rows = await fetch("SELECT code, name, description FROM achievements")
    return [dict(row) for row in rows]


async def get_achievement_by_code(code: str) -> dict | None:
    row = await fetchrow(
        "SELECT id, code, name, description FROM achievements WHERE code = $1",
        code,
    )
    return dict(row) if row else None


async def get_achievements_by_code(code: str) -> list[dict]:
    achievement = await get_achievement_by_code(code)
    return [achievement] if achievement else []


async def add_achievement(code: str, name: str, description: str) -> None:
    await execute(
        "INSERT INTO achievements(code, name, description) VALUES ($1, $2, $3) ON CONFLICT(code) DO NOTHING",
        code,
        name,
        description,
    )


async def update_achievement(achievement_code: str, name: str | None = None, description: str | None = None, conditions: str | None = None) -> None:
    achievement = await fetchrow("SELECT id FROM achievements WHERE code = $1", achievement_code)
    if achievement is None:
        raise ValueError(f"Achievement with code '{achievement_code}' does not exist.")
    if name is not None:
        await execute("UPDATE achievements SET name = $1 WHERE code = $2", name, achievement_code)
    if description is not None:
        await execute("UPDATE achievements SET description = $1 WHERE code = $2", description, achievement_code)
    if conditions is not None:
        await execute("UPDATE achievements SET conditions = $1 WHERE code = $2", conditions, achievement_code)


async def grant_achievement(user_id: int, achievement_code: str) -> None:
    achievement = await fetchrow("SELECT id FROM achievements WHERE code = $1", achievement_code)
    if achievement is None:
        raise ValueError(f"Achievement with code '{achievement_code}' does not exist.")
    await execute(
        """
        INSERT INTO user_achievements(user_id, achievement_id, obtained_at)
        VALUES ($1, $2, EXTRACT(EPOCH FROM NOW())::BIGINT)
        ON CONFLICT(user_id, achievement_id) DO NOTHING
        """,
        user_id,
        achievement["id"],
    )


async def revoke_achievement(user_id: int, achievement_code: str) -> None:
    achievement = await fetchrow("SELECT id FROM achievements WHERE code = $1", achievement_code)
    if achievement is None:
        raise ValueError(f"Achievement with code '{achievement_code}' does not exist.")
    await execute(
        "DELETE FROM user_achievements WHERE user_id = $1 AND achievement_id = $2",
        user_id,
        achievement["id"],
    )


async def get_user_achievements(user_id: int) -> list[dict]:
    rows = await fetch(
        """
        SELECT a.code, a.name, a.description, ua.obtained_at
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = $1
        """,
        user_id,
    )
    return [dict(row) for row in rows]
