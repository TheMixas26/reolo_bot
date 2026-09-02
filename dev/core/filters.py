from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from core import permissions


class HasPermission(BaseFilter):
    """Кастомный фильтр для проверки, тварь ты дрожащая или раво имеешь на конкретную команду
    
    Пример:
    
        from core.filters import HasPermission
        @router.message(Command("command"), HasPermission(context, "admin", command="command"))

    """

    def __init__(self, context, default: str = "admin", *, command: str | None = None):
        self.context = context
        self.default = default
        self.command = command

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if user is None:
            return False

        required = self.default
        if self.command:
            required = await permissions.get_required_role(self.command, default=self.default)

        role = await permissions.get_role(user.id, owner_id=self.context.admin_id)
        return permissions.has_rank(role, required)