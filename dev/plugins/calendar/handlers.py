from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from varibles.dialogue_loader import TEXT
from core.core_plugin.stats import log_command_usage


def register_handlers(context) -> Router:
    # TODO: texts.json
    router = Router(name="calendar-plugin")

    @router.message(Command("today"))
    async def imperial_today(message: Message):
        log_command_usage("predlojka", "today", message)
        try:
            from .service import calendar

            today = calendar.today()
            short_date = calendar.short()
            full_date = calendar.full()
            event = today["event"] if "event" in today else "Сегодня нет праздников."

            response = (
                "📅 Имперская дата сегодня:\n\n"
                f"Короткий формат: {short_date}\n"
                f"Полный формат: {full_date}\n"
                f"Праздник: {event}"
            )
            await message.reply(response)
        except Exception as error:
            context.logger.error(f"Ошибка в imperial_today: {error}")
            await message.reply(TEXT("err", "get_today_date"))

    @router.message(Command("nearest_event"))
    async def imperial_nearest_event(message: Message):
        log_command_usage("predlojka", "nearest_event", message)
        try:
            from .service import calendar

            events = calendar.next_events(3)
            response = "🎉 Ближайшие праздники Имперского календаря:\n\n"
            for event in events:
                response += (
                    f"{event['day']:02d} {event['month']} — "
                    f"{event['name']['title']} "
                    f"(через {event['daysLeft']} дн.)\n"
                )
            await message.reply(response)
        except Exception as error:
            context.logger.error(f"Ошибка в imperial_nearest_event: {error}")
            await message.reply(TEXT("err", "get_nearest_event"))

    @router.message(Command("all_events"))
    async def imperial_all_events(message: Message):
        log_command_usage("predlojka", "all_events", message)
        try:
            from .service import calendar

            events = calendar.all_events_with_countdown()
            response = "📜 Все праздники Имперского календаря:\n\n"
            for event in events:
                response += (
                    f"{event['day']:02d} {event['month']} — "
                    f"{event['name']['title']} "
                    f"(через {event['daysLeft']} дн.)\n"
                )
            await message.reply(response)
        except Exception as error:
            context.logger.error(f"Ошибка в imperial_all_events: {error}")
            await message.reply(TEXT("err", "get_all_events"))

    return router
