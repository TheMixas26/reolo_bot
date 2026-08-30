from database.connection import execute, fetch, fetchrow


async def upsert_birthday(user_id: int, name: str, day: int, month: int, year: int, username: str | None = None) -> None:
    await execute(
        """
        INSERT INTO birthdays(user_id, name, username, day, month, year)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT(user_id) DO UPDATE SET
            name = EXCLUDED.name,
            username = COALESCE(EXCLUDED.username, birthdays.username),
            day = EXCLUDED.day,
            month = EXCLUDED.month,
            year = EXCLUDED.year
        """,
        user_id,
        name,
        username,
        day,
        month,
        year,
    )


async def get_all_birthdays() -> list[dict]:
    rows = await fetch("SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays")
    return [dict(row) for row in rows]


async def update_birthday_name(user_id: int, name: str) -> None:
    await execute("UPDATE birthdays SET name = $1 WHERE user_id = $2", name, user_id)


async def get_birthday(user_id: int) -> dict | None:
    row = await fetchrow(
        "SELECT user_id, name, username, day, month, year, personal_notify FROM birthdays WHERE user_id = $1",
        user_id,
    )
    return dict(row) if row else None


async def set_personal_notify(user_id: int, enabled: bool) -> None:
    await execute("UPDATE birthdays SET personal_notify = $1 WHERE user_id = $2", enabled, user_id)
