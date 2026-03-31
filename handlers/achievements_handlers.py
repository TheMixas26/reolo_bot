from config import predlojka_bot, admin
from analytics.stats import log_command_usage, log_event
from database.sqlite_db import get_all_achievements, add_achievement, grant_achievement, revoke_achievement, get_user_achievements, get_balance, update_achievement


@predlojka_bot.message_handler(commands=['achievements'])
def list_achievements_command(message):
    log_command_usage("predlojka", "achievements", message)
    achievements = get_all_achievements()
    if not achievements:
        predlojka_bot.reply_to(message, "Пока что никаких достижений нет. (;￣▽￣)")
    else:
        response = "А вот и все доступные вам достижения:\n"
        for ach in achievements:
            response += f"- {ach['name']} (код: {ach['code']}): {ach['description']}\n"
        predlojka_bot.reply_to(message, response)



@predlojka_bot.message_handler(commands=['me'])
def get_achievements_command(message):
    log_command_usage("predlojka", "me", message)
    user_id = message.from_user.id
    achievements = get_user_achievements(user_id)
    balance = get_balance(user_id)

    if achievements:
        achievements_text = "Ваши достижения:\n"
        for ach in achievements:
            achievements_text += f"- {ach['name']}: {ach['description']} (получено: {ach['obtained_at']})\n"
    else:
        achievements_text = "У вас нет достижений. Надеюсь, что это только временное явление!)"

    balance_text = f"\nВаш баланс: {balance}" if balance is not None else "\nВаш баланс пока недоступен."

    predlojka_bot.reply_to(message, f"Здравствуйте, {message.from_user.first_name}! Рада, что вы заинтересовались собой!)\n\n{achievements_text}\n\n{balance_text}")




@predlojka_bot.message_handler(commands=['add_achievement'])
def add_achievement_command(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "add_achievement", message)

    try:
        command, data = message.text.split(' ', 1)

        code, name, description = [x.strip() for x in data.split('|', 2)]

        add_achievement(code, name, description)

        predlojka_bot.reply_to(
            message,
            f"Достижение '{name}' добавлено с кодом '{code}'! (・ω・)ゞ"
        )
        log_event("achievement_created", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"achievement_code": code})

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
    log_command_usage("predlojka", "grant_achievement", message)

    try:
        command, data = message.text.split(' ', 1)

        user_id_str, achievement_code = [x.strip() for x in data.split('|', 1)]
        user_id = int(user_id_str)

        grant_achievement(user_id, achievement_code)

        predlojka_bot.reply_to(
            message,
            f"Успешно выдала Достижение '{achievement_code}' пользователю {user_id}!"
        )
        log_event(
            "achievement_granted_manual",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"target_user_id": user_id, "achievement_code": achievement_code},
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
    log_command_usage("predlojka", "revoke_achievement", message)

    try:
        command, data = message.text.split(' ', 1)

        user_id_str, achievement_code = [x.strip() for x in data.split('|', 1)]
        user_id = int(user_id_str)

        revoke_achievement(user_id, achievement_code)

        predlojka_bot.reply_to(
            message,
            f"Достижение '{achievement_code}' конфисковано у пользователя {user_id}!)))"
        )
        log_event(
            "achievement_revoked",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"target_user_id": user_id, "achievement_code": achievement_code},
        )

    except ValueError:
        predlojka_bot.reply_to(
            message,
            "Формат:\n"
            "/revoke_achievement user_id | achievement_code"
        )


@predlojka_bot.message_handler(commands=['add_conditions'])
def add_conditions_command(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "add_conditions", message)

    try:
        command, data = message.text.split(' ', 1)

        achievement_code, conditions = [x.strip() for x in data.split('|', 1)]

        update_achievement(achievement_code, conditions=conditions)

        predlojka_bot.reply_to(
            message,
            f"Обновила условия достижения '{achievement_code}' на '{conditions}'."
        )
        log_event(
            "achievement_conditions_updated",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"achievement_code": achievement_code},
        )

    except ValueError:
        predlojka_bot.reply_to(
            message,
            "Формат:\n"
            "/add_conditions achievement_code | conditions"
        )
