from config import predlojka_bot, admin
from database.sqlite_db import achievements_list, add_achievement, grant_achievement, revoke_achievement, get_user_achievements, get_balance


@predlojka_bot.message_handler(commands=['achievements'])
def list_achievements_command(message):
    achievements = achievements_list('')
    if not achievements:
        predlojka_bot.reply_to(message, "Пока нет достижений.")
    else:
        response = "Все доступные достижения:\n"
        for ach in achievements:
            response += f"- {ach['name']} (код: {ach['code']}): {ach['description']}\n"
        predlojka_bot.reply_to(message, response)



@predlojka_bot.message_handler(commands=['me'])
def get_achievements_command(message):
    user_id = message.from_user.id
    achievements = get_user_achievements(user_id)
    balance = get_balance(user_id)

    if achievements:
        achievements_text = "Ваши достижения:\n"
        for ach in achievements:
            achievements_text += f"- {ach['name']}: {ach['description']} (получено: {ach['obtained_at']})\n"
    else:
        achievements_text = "У вас нет достижений. Надеюсь, что это только временное явление!)"

    if balance is not None:
        balance_text = f"\nВаш баланс: {balance}"

    predlojka_bot.reply_to(message, f"Здравствуйте, {message.from_user.first_name}! Рад, что вы заинтересовались собой!\n\n{achievements_text}\n\n{balance_text}")




@predlojka_bot.message_handler(commands=['add_achievement'])
def add_achievement_command(message):

    if message.from_user.id != admin:
        return

    try:
        command, data = message.text.split(' ', 1)

        code, name, description = [x.strip() for x in data.split('|', 2)]

        add_achievement(code, name, description)

        predlojka_bot.reply_to(
            message,
            f"Достижение '{name}' добавлено с кодом '{code}'."
        )

    except ValueError:
        predlojka_bot.reply_to(
            message,
            "Формат:\n"
            "/add_achievement code | name | description"
        )

@predlojka_bot.message_handler(commands=['grant_achievement'])
def grant_achievement_command(message):

    if message.from_user.id != admin:
        return

    try:
        command, data = message.text.split(' ', 1)

        user_id_str, achievement_code = [x.strip() for x in data.split('|', 1)]
        user_id = int(user_id_str)

        grant_achievement(user_id, achievement_code)

        predlojka_bot.reply_to(
            message,
            f"Достижение '{achievement_code}' выдано пользователю {user_id}."
        )

    except ValueError:
        predlojka_bot.reply_to(
            message,
            "Формат:\n"
            "/grant_achievement user_id | achievement_code"
        )


@predlojka_bot.message_handler(commands=['revoke_achievement'])
def revoke_achievement_command(message):
    if message.from_user.id != admin:
        return

    try:
        command, data = message.text.split(' ', 1)

        user_id_str, achievement_code = [x.strip() for x in data.split('|', 1)]
        user_id = int(user_id_str)

        revoke_achievement(user_id, achievement_code)

        predlojka_bot.reply_to(
            message,
            f"Достижение '{achievement_code}' отозвано у пользователя {user_id}."
        )

    except ValueError:
        predlojka_bot.reply_to(
            message,
            "Формат:\n"
            "/revoke_achievement user_id | achievement_code"
        )