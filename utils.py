from random import choice
from telebot import types

def thx_for_message(user_name, mes_type):
    
    variants_v = [
        f"Спасибо за ваше сообщение, {user_name}!!!",
        f"Спасибо за новый пост, {user_name}!!!",
        f"Канал Жив благодаря таким, как вы, {user_name}. Спасибо!!!",
        f"Отличный вклад, {user_name}! Так держать!",
        f"Ваше сообщение - как глоток свежего воздуха, {user_name}. Благодарю!",
        f"{user_name}, вы делаете этот канал лучше. Спасибо за активность!",
        f"Без вас здесь было бы скучно, {user_name}. Огромное спасибо!",
        f"Каждое ваше слово - на вес золота, {user_name}. Ценим!",
        f"{user_name}, вы - двигатель канала. Спасибо за ваш пост!",
        f"Спасибо, что не даёте нам заглохнуть, {user_name}!"
    ]

    variants_q = [
        f"Спасибо за ваш вопрос, {user_name}!!!",
        f"{user_name}, мне теперь тоже интересно, что ответит админ!",
        f"К ему такое любопытсво, {user_name}?) Впрочем, неважно, моё дело - передать вопрос!",
        f"{user_name}, вопрос зафиксирован! Теперь ждём мудрого ответа сверху :)",
        f"Любопытненько, {user_name}... Передаю вопрос дальше!",
        f"О, отличный вопрос, {user_name}. Сам жду, что скажет админ!",
        f"Записал ваш вопрос, {user_name}. Надеюсь, админ не будет злиться :)",
        f"Любопытство — двигатель прогресса, {user_name}. Вопрос ушёл в эфир!",
        f"{user_name}, а ведь вопрос-то серьёзный. Давайте спросим у админа!",
        f"Ну всё, {user_name}, теперь админ обязан ответить! Интригааа...",
        f"{user_name}, ты хоть про подвалы так не спроси... Отправил вопрос, ждём ответ!",
    ]

    if mes_type == '!': return choice(variants_v)
    elif mes_type == '?': return choice(variants_q)


def get_commads_for_set(who_ask):
    default_commands = [
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("help", "Помощь"),
        types.BotCommand("changelog", "Инфо об обновлении"),
        types.BotCommand("bank", "Войти в банк"),
        types.BotCommand("battle", "Запустить простейший бой"),
        types.BotCommand("stats", "Узнать статы"),
        types.BotCommand("personal_notifications", "вкл/выкл личные уведомления о дне рождения"),
        types.BotCommand("add_birthday", "Добивить ваш день рождения в базу")
    ]

    admin_commands = [
        types.BotCommand("send_daily", "Принудиткльно выслать ежедневки"),
        types.BotCommand("send_personal_daily", "Принудительно выслать личные ежедневки"),
        types.BotCommand("add_birthday_by_username", "Принудительно добавить ДР пользователю"),
        types.BotCommand("setcmd", "Установить команды в меню"),
        types.BotCommand("edit_currency", "Изменить курс валют")
    ]

    if who_ask == 'user': return default_commands
    elif who_ask == 'admin': return default_commands + admin_commands
    else: return default_commands