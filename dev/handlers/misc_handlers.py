from config import predlojka_bot, admin, channel
from analytics.stats import log_command_usage
from posting.runtime import predlojka_telegram_adapter


@predlojka_bot.message_handler(commands=['send_smth'])
def handle_send_personal_daily(message):
    log_command_usage("predlojka", "send_smth", message)
    if message.from_user.id != admin:
        return
    command_text = message.text.replace('/send_smth', '').strip()

    try:
        user_id_str, text_to_send = command_text.split('|', 1)  
        user_id = int(user_id_str.strip())
        text_to_send = text_to_send.strip()
    except ValueError:
        predlojka_telegram_adapter.reply_to(message, "Ошибка формата. Используйте: /send_smth ID|текст сообщения")
        return
    except Exception as e:
        predlojka_telegram_adapter.reply_to(message, f"Произошла ошибка: {e}")
        return

    try:
        predlojka_telegram_adapter.send_message(user_id, text_to_send)
        # Подтверждаем успешную отправку
        predlojka_telegram_adapter.reply_to(
            message,
            f"Сообщение успешно отправлено получателю с ID {user_id}."
        )
    except Exception as e:
       
        predlojka_telegram_adapter.reply_to(
            message,
            f"Не удалось отправить сообщение получателю с ID {user_id}. Ошибка: {e}"
        )




@predlojka_bot.message_handler(commands=['today'])
def imperial_today(message):
    log_command_usage("predlojka", "today", message)
    try:
        from config import calendar

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
        print(f"Ошибка в imperial_today: {e}")
        predlojka_telegram_adapter.reply_to(message, "Извините, но получить сегодняшнюю имперскую дату не получилось... (´-﹏-；)")



@predlojka_bot.message_handler(commands=['nearest_event'])
def imperial_nearest_event(message):
    log_command_usage("predlojka", "nearest_event", message)
    try:
        from config import calendar

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
        print(f"Ошибка в imperial_nearest_event: {e}")
        predlojka_telegram_adapter.reply_to(
            message,
            "Простите, но получить ближайшие праздники Имперского календаря не получилось... (╯_╰)"
        )


@predlojka_bot.message_handler(commands=['all_events'])
def imperial_all_events(message):
    log_command_usage("predlojka", "all_events", message)
    try:
        from config import calendar

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
        print(f"Ошибка в imperial_all_events: {e}")
        predlojka_telegram_adapter.reply_to(
            message,
            "Прошу прощения, но я не смогла получить все праздники Имперского календаря... (;︵;)"
        )
