from config import predlojka_bot, admin, channel


@predlojka_bot.message_handler(commands=['send_to_tatyana_smth'])
def handle_send_personal_daily(message):

    text_ls = "Здравствуйте, Татьяна! Кажется, у вас сегодня день рождения... Если конечно мои подвальные записи не врут)\n\nМы всей Империей вас поздравляем! +1000 соуиального рейтинга и бесчисленное вам уважение!\n\nСпасибо вам за все ваши посты в Предложке (то есть, отпрвленные мне), мне бесконечно приятно, что наш канал живёт благодаря таким пользователям, как вы! С праздником вас, Татьяна!"

    text_ch = "Дорогие подписчкики! Сегодня случилось неверотяное!!! Сегодня день рождения у нашего дорогого подпчискика Татьяны!!!\n\nВы наверняка видели посты от Татьяны!)) Она очень преданный подписчик!\n\nДавайте дружно поздравим её в комментариях!!!\n\nС праздником, Татьяна!"

    if message.from_user.id != admin:
        return
    try:
        predlojka_bot.send_message(538339037, text_ls)
        predlojka_bot.send_message(channel, text_ch)
    except Exception as e:
        print(e)



@predlojka_bot.message_handler(commands=['today'])
def imperial_today(message):
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

        predlojka_bot.reply_to(message, response)

    except Exception as e:
        print(f"Ошибка в imperial_today: {e}")
        predlojka_bot.reply_to(message, "Не удалось получить имперскую дату сегодня.")



@predlojka_bot.message_handler(commands=['nearest_event'])
def imperial_nearest_event(message):
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

        predlojka_bot.reply_to(message, response)

    except Exception as e:
        print(f"Ошибка в imperial_nearest_event: {e}")
        predlojka_bot.reply_to(
            message,
            "Не удалось получить ближайшие праздники Имперского календаря."
        )


@predlojka_bot.message_handler(commands=['all_events'])
def imperial_all_events(message):
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

        predlojka_bot.reply_to(message, response)

    except Exception as e:
        print(f"Ошибка в imperial_all_events: {e}")
        predlojka_bot.reply_to(
            message,
            "Не удалось получить все праздники Имперского календаря."
        )