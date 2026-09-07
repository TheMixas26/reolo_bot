from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.core_plugin.stats import log_command_usage
from .jobs import send_weather
from varibles import TEXT


def register_handlers(context):
    router = Router(name="weather-handlers")

    @router.message(Command("send_weather"))
    async def command_to_send_weather(message: Message):
        if message.from_user.id != context.admin_id:
            await message.answer(TEXT("not_an_admin"))
            return
        log_command_usage("predlojka", "send_weather", message)
        await send_weather(context)
        await message.reply(TEXT("forced_weather"))

    
    # TODO: команда, которая будет отправлять прогноз ответом,
    # TODO: у пользователя должна быть возможность выбрать город
    # TODO: или типа того + сделать ./jobs.py:send_weather() более унифицированным
    @router.message(Command("weather", "forecast"))
    async def weather_command(message: Message):
        return


    return router
