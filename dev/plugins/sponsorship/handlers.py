from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from varibles import TEXT
import os
from pathlib import Path 


def register_handlers(context):
    admin = context.admin_id
    router = Router(name="sponsorship-plugin")

    @router.message(Command("allies"))
    async def allied_channels(message: Message):
        current_dir = Path(__file__).parent
        file_path = current_dir / "allies.txt"

        with open(file_path, "r", encoding="utf-8") as f:
            await message.reply("\n".join(f.readlines()))


    @router.message(Command("become_ally"))
    async def become_an_ally(message: Message):
        await message.reply(TEXT("become_ally"))

    return router
