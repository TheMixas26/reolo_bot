"""
AI desc: 

Права доступа поверх ролей: owner > admin > trusted > member.

owner всегда один — это context.admin_id из конфига, в БД он не хранится.
Остальные роли назначаются через set_role() (см. команду /setrole в
admin_utils) и хранятся в Postgres, так что переживают рестарт бота.

Отдельно — command_permissions: какая роль нужна для конкретной команды.
Если для команды нет записи, действует default, который передаёт сам
хендлер при объявлении фильтра. Это даёт то самое "вдруг захочу ограничить
некоторые функции" — правишь одной командой /setperm, без деплоя.

Инициализация таблиц: init_permission_tables() надо вызвать один раз при
старте, например из CorePlugin.setup(context) в main.py, аналогично тому,
как другие плагины поднимают свои таблицы.
"""

from __future__ import annotations

from database.connection import execute, fetchval

ROLE_RANK = {
    "member": 0,
    "trusted": 1,
    "admin": 2,
    "owner": 3,
}

# !!! ОСНОВА ДЛЯ #59
# TODO: Развить идею для #59


async def init_permission_tables() -> None:
    await execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id BIGINT PRIMARY KEY,
            role TEXT NOT NULL DEFAULT 'member'
        );
        """
    )
    await execute(
        """
        CREATE TABLE IF NOT EXISTS command_permissions (
            command TEXT PRIMARY KEY,
            required_role TEXT NOT NULL
        );
        """
    )


async def get_role(user_id: int, *, owner_id: int) -> str:
    if user_id == owner_id:
        return "owner"
    role = await fetchval("SELECT role FROM user_roles WHERE user_id = $1", user_id)
    return role or "member"


async def set_role(user_id: int, role: str) -> None:
    if role not in ROLE_RANK:
        raise ValueError(f"неизвестная роль: {role} (доступны: {', '.join(ROLE_RANK)})")
    await execute(
        """
        INSERT INTO user_roles(user_id, role) VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET role = excluded.role
        """,
        user_id, role,
    )


async def get_required_role(command: str, *, default: str) -> str:
    role = await fetchval(
        "SELECT required_role FROM command_permissions WHERE command = $1", command
    )
    return role or default


async def set_required_role(command: str, role: str) -> None:
    if role not in ROLE_RANK:
        raise ValueError(f"неизвестная роль: {role} (доступны: {', '.join(ROLE_RANK)})")
    await execute(
        """
        INSERT INTO command_permissions(command, required_role) VALUES ($1, $2)
        ON CONFLICT (command) DO UPDATE SET required_role = excluded.required_role
        """,
        command, role,
    )


def has_rank(user_role: str, required_role: str) -> bool:
    return ROLE_RANK.get(user_role, 0) >= ROLE_RANK.get(required_role, 0)