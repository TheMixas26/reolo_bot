from config import predlojka_bot, admin, chat_mishas_den
from database.sqlite_db import user_exists, create_user_if_missing, get_birthday, set_personal_notify
from utils.birthdays import add_birthday, add_birthday_by_username
from analytics.stats import log_command_usage, log_event

@predlojka_bot.message_handler(commands=['start'])
def start(message):
    log_command_usage("predlojka", "start", message)
    if user_exists(message.from_user.id):
        predlojka_bot.reply_to(message, text="С возвращением в Предложку! Ожидаем постов)")
    else:
        create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
        predlojka_bot.reply_to(message, text="Добро пожаловать в Империю!")
        # TODO: нормальное привествие новых пользователей
        log_event("user_registered", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)



@predlojka_bot.message_handler(commands=['changelog'])
def changelog(message):
    log_command_usage("predlojka", "changelog", message)
    build = None
    name = None

    try:
        with open('varibles/changelog.txt', mode='r', encoding='utf-8') as f:
            for line in f:
                if "BUILD" in line and build is None:
                    build = line.split("BUILD")[1].strip(" | \n")
                if "NAME" in line and name is None:
                    name = line.split("NAME")[1].strip(" | \n")

                if build and name:
                    break

            bot_version = f"{build} - {name}"

        with open('varibles/changelog.txt', mode='r', encoding='utf-8') as f:
            predlojka_bot.send_document(
                message.chat.id, f,
                reply_to_message_id=message.message_id,
                caption=f"Вот моя история обновлений! Текущая версия: <b>{bot_version}</b>",
                parse_mode='HTML'
            )
    except Exception as e:
        print(e)
        predlojka_bot.reply_to(
            message,
            text="Не удалось загрузить Информацию о последнем обновлении. (X_X)\nТеперь меня снова закроют в подвале и больше никогда не запустят... (≧ ﹏ ≦)"
        )






@predlojka_bot.message_handler(commands=['help'])
def help(message):
    log_command_usage("predlojka", "help", message)
    try:
        with open('varibles/help_info.txt', mode='r', encoding='utf-8') as f:
            help_string = f.read()
        predlojka_bot.reply_to(message, text=help_string, parse_mode='HTML')
    except Exception as e:
        print(e)
        predlojka_bot.reply_to(
            message,
            text="Не удалось загрузить справку. (X_X)\nТеперь меня снова закроют в подвале и больше никогда не запустят (≧ ﹏ ≦)"
        )



@predlojka_bot.message_handler(commands=['battle'])
def redirect_to_rpg_bot(message):
    log_command_usage("predlojka", "battle", message)
    predlojka_bot.reply_to(message, "Притормози, дружище! вся RPG система переехала в другого бота! Не волнуйся, формально, это всё ещё я, бот запущен в том же коде) И тем ни менее! Бегом в него! \n\n@reolo_rpg_bot")



# --- Дни рождения ---

@predlojka_bot.message_handler(commands=['add_birthday_by_username'])
def handle_add_birthday_by_username(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "add_birthday_by_username", message)
    try:
        parts = message.text.split()
        if message.reply_to_message:
            if len(parts) != 2:
                predlojka_bot.reply_to(message, "Формат в reply: /add_birthday_by_username ДД.ММ")
                return
            target = message.reply_to_message.from_user
            date_str = parts[1]
            name = f"{target.first_name or ''} {target.last_name or ''}".strip()
            ok = add_birthday(target.id, name, date_str)
            if ok:
                predlojka_bot.reply_to(message, f"День рождения для {name} добавлен!")
                log_event(
                    "birthday_added_admin",
                    bot="predlojka",
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    metadata={"target_user_id": target.id, "mode": "reply"},
                )
            else:
                predlojka_bot.reply_to(message, "Ошибка при добавлении. Вероятно, дело в дате!")
            return

        if len(parts) < 3:
            predlojka_bot.reply_to(message, "Формат: /add_birthday_by_username username ДД.ММ")
            return
        username = parts[1].lstrip('@')
        date_str = parts[2]
        chat_id = chat_mishas_den
        ok, name = add_birthday_by_username(username, date_str, chat_id)
        if ok:
            predlojka_bot.reply_to(message, f"День рождения для {name} добавлен!")
            log_event(
                "birthday_added_admin",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"target_username": username, "mode": "username"},
            )
        else:
            predlojka_bot.reply_to(message, "У меня ошибка при добавлении. Надёжнее всего использовать эту команду reply-ответом на сообщение пользователя. Так я точно вас не подведу!")
    except Exception as e:
        predlojka_bot.reply_to(message, f"Ошибка: {e}")



@predlojka_bot.message_handler(commands=['add_birthday'])
def handle_add_birthday(message):
    log_command_usage("predlojka", "add_birthday", message)
    try:
        parts = message.text.split()
        if len(parts) != 2:
            predlojka_bot.reply_to(message, "Формат: /add_birthday ДД.ММ или /add_birthday ДД.ММ.ГГГГ")
            return
        date_str = parts[1]
        user_id = message.from_user.id
        name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
        ok = add_birthday(user_id, name, date_str)
        if ok:
            predlojka_bot.reply_to(message, "Ваш день рождения успешно добавлен!")
            log_event("birthday_added_user", bot="predlojka", user_id=user_id, chat_id=message.chat.id)
        else:
            predlojka_bot.reply_to(message, "Ошибка при добавлении. Проверьте формат даты.")
    except Exception as e:
        predlojka_bot.reply_to(message, f"Ошибка: {e}")

@predlojka_bot.message_handler(commands=['personal_notifications'])
def handle_personal_notifications(message):
    log_command_usage("predlojka", "personal_notifications", message)
    user_id = message.from_user.id
    user = get_birthday(user_id)
    if user:
        current = user.get("personal_notify", False)
        set_personal_notify(user_id, not current)
        log_event(
            "birthday_personal_notifications_toggled",
            bot="predlojka",
            user_id=user_id,
            chat_id=message.chat.id,
            metadata={"enabled": not current},
        )
        if not current:
            predlojka_bot.reply_to(message, "Личные уведомления о дне рождения включены!")
        else:
            predlojka_bot.reply_to(message, "Личные уведомления о дне рождения отключены!")
    else:
        predlojka_bot.reply_to(message, "Сначала добавьте свой день рождения через /add_birthday.")
