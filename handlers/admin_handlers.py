from config import predlojka_bot, admin, channel
from telebot import types
from bank import edit_currency_info
from utils.utils import get_commads_for_set
from utils.birthdays import send_daily_birthdays, send_personal_birthday_notifications

@predlojka_bot.message_handler(commands=['edit_currency'])
def editing_currency(message):
    if message.chat.id == admin:
        predlojka_bot.reply_to(message, "Скинь циферки, баты и рубли через запятую")
        predlojka_bot.register_next_step_handler(message, editing_currency2)
    else:
        predlojka_bot.reply_to(message, "Экономику не ломай")

def editing_currency2(message):
    try:
        purumpurum = message.text.split(",")
        a = int(purumpurum[0])
        b = int(purumpurum[1])
        edit_currency_info(message, a, b)
    except Exception:
        predlojka_bot.reply_to(message, "Не вышло")


@predlojka_bot.message_handler(commands=['setcmd'])
def set_commands(message):
    if message.from_user.id != admin:
        return
    
    scope = types.BotCommandScopeChat(admin)

    predlojka_bot.set_my_commands(get_commads_for_set('user'))
    predlojka_bot.set_my_commands(
        get_commads_for_set('admin'),
        scope=scope
    )

    predlojka_bot.reply_to(message, "Команды обновлены!")



@predlojka_bot.message_handler(commands=['send_daily'])
def handle_send_daily(message):
    if message.from_user.id != admin:
        return
    try:
        send_daily_birthdays()
    except Exception as e:
        print(e)

@predlojka_bot.message_handler(commands=['send_personal_daily'])
def handle_send_personal_daily(message):
    if message.from_user.id != admin:
        return
    try:
        send_personal_birthday_notifications()
    except Exception as e:
        print(e)


@predlojka_bot.message_handler(commands=['fake_post'])
def handle_fake_post(message):
    if message.from_user.id != admin:
        return
    predlojka_bot.reply_to(message, "Отлично, напиши пост \(подпись от человека весит на тебе\)\n\nНа всякий напоминаю, `👤 {имя}`", parse_mode="MarkdownV2")
    predlojka_bot.register_next_step_handler(message, handle_fake_post2)

def handle_fake_post2(message):
    if message.from_user.id != admin:
        return
    try:
        predlojka_bot.send_message(channel, message.text)
        predlojka_bot.send_message(message.chat.id, "Готово! Пост улетел. Удачи с махинациями)))")
    except Exception as e:
        predlojka_bot.send_message(message.chat.id, f"Ошибка при отправке поста: {e}")