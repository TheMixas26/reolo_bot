from aiogram import Router
from aiogram.filters import Command

from core.core_plugin.stats import log_command_usage
from .jobs import send_weather
from varibles.dialogue_loader import TEXT


def register_handlers(context):
    router = Router(name="weather-handlers")

    @router.message(Command("send_weather"))
    async def command_to_send_weather(message):
        if message.from_user.id != context.admin_id:
            await message.answer(TEXT("not_an_admin"))
            return
        log_command_usage("predlojka", "send_weather", message)
        await send_weather(context)
        await message.reply(TEXT("forced_weather"))


    return router
