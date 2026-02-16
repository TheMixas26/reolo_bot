from config import predlojka_bot, db, bot_version, admin, chat_mishas_den
from tinydb import Query
from birthdays import add_birthday, add_birthday_by_username

@predlojka_bot.message_handler(commands=['start'])
def start(message):
    if db.contains(Query().id == message.from_user.id):
        predlojka_bot.reply_to(message, text="С возвращением в Предложку! Ожидаем постов)")
    else:
        db.insert({
            'id': message.from_user.id,
            'name': f'{message.from_user.first_name}',
            'last_name': f'{message.from_user.last_name}',
            'balance': 0
        })
        predlojka_bot.reply_to(message, text="Добро пожаловать в Империю!")

@predlojka_bot.message_handler(commands=['changelog'])
def changelog(message):
    try:
        with open('changelog.txt', mode='r', encoding='utf-8') as f:
            predlojka_bot.send_document(
                message.chat.id, f,
                reply_to_message_id=message.message_id,
                caption=f"Вот моя история обновлений! Текущая версия - <b>{bot_version}</b>",
                parse_mode='HTML'
            )
    except Exception as e:
        print(e)
        predlojka_bot.reply_to(
            message,
            text="Не удалось загрузить Информацию о последнем обновлении. (X_X)\nТеперь меня снова закроют в подвале и больше никогда не запустят (≧ ﹏ ≦)"
        )






@predlojka_bot.message_handler(commands=['help'])
def help(message):
    try:
        with open('help_info.txt', mode='r', encoding='utf-8') as f:
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
    predlojka_bot.reply_to(message, "Притормози, дружище! вся RPG система переехала в другого бота! Не волнуйся, формально, это всё ещё я, бот запущен в том же коде) И тем ни менее! Бегогм в него! \n\n@reolo_rpg_bot")



# --- Дни рождения ---

@predlojka_bot.message_handler(commands=['add_birthday_by_username'])
def handle_add_birthday_by_username(message):
    if message.from_user.id != admin:
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            predlojka_bot.reply_to(message, "Формат: /add_birthday_by_username username ДД.ММ")
            return
        username = parts[1].lstrip('@')
        date_str = parts[2]
        chat_id = chat_mishas_den
        ok, name = add_birthday_by_username(username, date_str, chat_id)
        if ok:
            predlojka_bot.reply_to(message, f"День рождения для {name} добавлен!")
        else:
            predlojka_bot.reply_to(message, "Ошибка при добавлении. Проверьте username и дату.")
    except Exception as e:
        predlojka_bot.reply_to(message, f"Ошибка: {e}")



@predlojka_bot.message_handler(commands=['add_birthday'])
def handle_add_birthday(message):
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
        else:
            predlojka_bot.reply_to(message, "Ошибка при добавлении. Проверьте формат даты.")
    except Exception as e:
        predlojka_bot.reply_to(message, f"Ошибка: {e}")

@predlojka_bot.message_handler(commands=['personal_notifications'])
def handle_personal_notifications(message):
    user_id = message.from_user.id
    table = db.table("birthdays")
    user = table.get(Query().user_id == user_id)
    if user:
        current = user.get("personal_notify", False)
        table.update({"personal_notify": not current}, Query().user_id == user_id)
        if not current:
            predlojka_bot.reply_to(message, "Личные уведомления о дне рождения включены!")
        else:
            predlojka_bot.reply_to(message, "Личные уведомления о дне рождения отключены!")
    else:
        predlojka_bot.reply_to(message, "Сначала добавьте свой день рождения через /add_birthday.")


