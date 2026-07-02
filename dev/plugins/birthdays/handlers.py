from dev.core.core_plugin.stats import log_command_usage, log_event
from varibles.dialogue_loader import TEXT
from .service import send_personal_birthday_notifications, add_birthday, add_birthday_by_username, send_daily_birthdays, get_user_birthday, change_personal_notify



def register_handlers(context):
    logger = context.logger_factory("birthdays", persona="Никитос")
    bot = context.predlojka_bot
    predlojka_telegram_adapter = context.tg_adapter
    admin = context.admin_id


    logger.say("От имени плагина дней рождений регестрирую команды...")
    # ------- Handlers registering -----------

    def handle_add_birthday_by_username(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "add_birthday_by_username", message)
        try:
            parts = message.text.split()
            if message.reply_to_message:
                if len(parts) != 2:
                    predlojka_telegram_adapter.reply_to(message, "Формат в reply: /add_birthday_by_username ДД.ММ")
                    return
                target = message.reply_to_message.from_user
                date_str = parts[1]
                name = f"{target.first_name or ''} {target.last_name or ''}".strip()
                ok = add_birthday(context, target.id, name, date_str)
                if ok:
                    predlojka_telegram_adapter.reply_to(message, f"День рождения для {name} добавлен!")
                    log_event(
                        "birthday_added_admin",
                        bot="predlojka",
                        user_id=message.from_user.id,
                        chat_id=message.chat.id,
                        metadata={"target_user_id": target.id, "mode": "reply"},
                    )
                else:
                    predlojka_telegram_adapter.reply_to(message, "Ошибка при добавлении. Вероятно, дело в дате!")
                return

            if len(parts) < 3:
                predlojka_telegram_adapter.reply_to(message, "Формат: /add_birthday_by_username username ДД.ММ")
                return
            username = parts[1].lstrip('@')
            date_str = parts[2]
            chat_id = context.config.chat_mishas_den
            ok, name = add_birthday_by_username(context, username, date_str, chat_id)
            if ok:
                predlojka_telegram_adapter.reply_to(message, f"День рождения для {name} добавлен!")
                log_event(
                    "birthday_added_admin",
                    bot="predlojka",
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    metadata={"target_username": username, "mode": "username"},
                )
            else:
                predlojka_telegram_adapter.reply_to(message, TEXT("err", "bday_adding"))
        except Exception as e:
            predlojka_telegram_adapter.reply_to(message, f"Ошибка: {e}")


    def handle_add_birthday(message):
        log_command_usage("predlojka", "add_birthday", message)
        try:
            parts = message.text.split()
            if len(parts) != 2:
                predlojka_telegram_adapter.reply_to(message, "Формат: /add_birthday ДД.ММ или /add_birthday ДД.ММ.ГГГГ")
                return
            date_str = parts[1]
            user_id = message.from_user.id
            name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
            ok = add_birthday(context, user_id, name, date_str)
            if ok:
                predlojka_telegram_adapter.reply_to(message, "Ваш день рождения успешно добавлен!")
                log_event("birthday_added_user", bot="predlojka", user_id=user_id, chat_id=message.chat.id)
            else:
                predlojka_telegram_adapter.reply_to(message, TEXT("err", "check_date_format"))
        except Exception as e:
            predlojka_telegram_adapter.reply_to(message, f"Ошибка: {e}")

    def handle_personal_notifications(message):
        log_command_usage("predlojka", "personal_notifications", message)
        user_id = message.from_user.id
        user = get_user_birthday(user_id)
        if user:
            current = user.get("personal_notify", False)
            change_personal_notify(user_id, not current)
            log_event(
                "birthday_personal_notifications_toggled",
                bot="predlojka",
                user_id=user_id,
                chat_id=message.chat.id,
                metadata={"enabled": not current},
            )
            if not current:
                predlojka_telegram_adapter.reply_to(message, TEXT("personal_bday_enabled"))
            else:
                predlojka_telegram_adapter.reply_to(message, TEXT("personal_bday_disabled"))
        else:
            predlojka_telegram_adapter.reply_to(message, TEXT("add_bday_before"))

    def handle_send_personal_daily(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "send_personal_daily", message)
        try:
            send_personal_birthday_notifications(context)
        except Exception as e:
            logger.say(e, "error")

    
    def handle_send_daily(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "send_daily", message)
        try:
            send_daily_birthdays(context)
        except Exception as e:
            logger.say(e, "error")





    # ---------- Command registering ------------


    bot.register_message_handler(
        handle_add_birthday,
        commands=["add_birthday"]
    )

    bot.register_message_handler(
        handle_add_birthday_by_username,
        commands=["add_birthday_by_username"]
    )

    bot.register_message_handler(
        handle_personal_notifications,
        commands=["personal_notifications"]
    )

    bot.register_message_handler(
        handle_send_personal_daily,
        commands=['send_personal_daily']
    )

    bot.register_message_handler(
        handle_send_daily,
        commands=['send_daily']
    )

    logger.say("Все команды добавлены!")