from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from varibles import TEXT


def register_handlers(context):
    admin = context.admin_id
    router = Router(name="sponsorship-plugin")

    @router.message(Command("allies"))
    async def allied_channels(message: Message):
        await message.reply(TEXT("allied_channels"))


    @router.message(Command("become_ally"))
    async def become_an_ally(message: Message):
        await message.reply(TEXT("become_ally"))

    return router
