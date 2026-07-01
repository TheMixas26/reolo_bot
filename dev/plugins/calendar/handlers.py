from varibles.dialogue_loader import TEXT
from analytics.stats import log_command_usage


def register_handlers(context):
    predlojka_telegram_adapter = context.tg_adapter
    predlojka_bot = context.predlojka_bot

    def imperial_today(message):
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

            predlojka_telegram_adapter.reply_to(message, response)

        except Exception as e:
            context.logger.error(f"Ошибка в imperial_today: {e}")
            predlojka_telegram_adapter.reply_to(message, TEXT("err", "get_today_date"))

    def imperial_nearest_event(message):
        log_command_usage("predlojka", "nearest_event", message)
        try:
            from .service import calendar

            events = calendar.next_events(3)
            response = "🎉 Ближайшие праздники Имперского календаря:\n\n"

            for e in events:
                response += (
                    f"{e['day']:02d} {e['month']} — "
                    f"{e['name']['title']} "
                    f"(через {e['daysLeft']} дн.)\n"
                )

            predlojka_telegram_adapter.reply_to(message, response)

        except Exception as e:
            context.logger.error(f"Ошибка в imperial_nearest_event: {e}")
            predlojka_telegram_adapter.reply_to(
                message,
                TEXT("err", "get_nearest_event")
            )

    def imperial_all_events(message):
        log_command_usage("predlojka", "all_events", message)
        try:
            from .service import calendar

            events = calendar.all_events_with_countdown()
            response = "📜 Все праздники Имперского календаря:\n\n"

            for e in events:
                response += (
                    f"{e['day']:02d} {e['month']} — "
                    f"{e['name']['title']} "
                    f"(через {e['daysLeft']} дн.)\n"
                )

            predlojka_telegram_adapter.reply_to(message, response)

        except Exception as e:
            context.logger.error(f"Ошибка в imperial_all_events: {e}")
            predlojka_telegram_adapter.reply_to(
                message,
                TEXT("err", "get_all_events")
            )


    predlojka_bot.register_message_handler(
        imperial_today,
        commands=['today']
    )

    predlojka_bot.register_message_handler(
        imperial_nearest_event,
        commands=['nearest_event']
    )

    predlojka_bot.register_message_handler(
        imperial_all_events,
        commands=['all_events']
    )