from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def register_handlers(context) -> Router:
    router = Router(name="template-plugin")
    admin_id = context.admin_id

    @router.message(Command("template_test"))
    async def handle_template_test(message: Message):
        if message.from_user.id != admin_id:
            return
        await message.reply("Шаблон плагина работает.")

    return router