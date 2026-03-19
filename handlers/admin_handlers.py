from config import predlojka_bot, admin, channel
from telebot import types
from bank import edit_currency_info
from utils.utils import get_commads_for_set, backupDB
from utils.birthdays import send_daily_birthdays, send_personal_birthday_notifications
from database.sqlite_db import get_all_users

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
    predlojka_bot.reply_to(message, "Отлично, напиши пост \(подпись от человека висит на тебе\)\n\nНа всякий напоминаю, `👤 {имя}`", parse_mode="MarkdownV2")
    predlojka_bot.register_next_step_handler(message, handle_fake_post2)

def handle_fake_post2(message):
    if message.from_user.id != admin:
        return
    try:
        predlojka_bot.send_message(channel, message.text)
        predlojka_bot.send_message(message.chat.id, "Готово! Пост улетел. Удачи с махинациями)))")
    except Exception as e:
        predlojka_bot.send_message(message.chat.id, f"Ошибка при отправке поста: {e}")



@predlojka_bot.message_handler(commands=['stop_bot'])
def stop_bot(message):
    if message.from_user.id != admin:
        return
    predlojka_bot.reply_to(message, "Останавливаю бота...")
    SystemExit("Бот остановлен администратором")



@predlojka_bot.message_handler(commands=['broadcast'])
def public_notify_command(message):
    if message.from_user.id != admin:
        return
    predlojka_bot.reply_to(message, "Ого! У нас тут рассылка намечается! Напиши сообщение, которое хочешь разослать всем пользователям. А потом доверься мне))")
    predlojka_bot.register_next_step_handler(message, handle_public_notify)


def handle_public_notify(message):
    if message.from_user.id != admin:
        return
    try:
        users = get_all_users()
        for user in users:
            try:
                predlojka_bot.send_message(user['user_id'], message.text)
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
        predlojka_bot.reply_to(message, "Рассылка завершена!")
    except Exception as e:
        predlojka_bot.reply_to(message, f"Ошибка при рассылке: {e}")



@predlojka_bot.message_handler(commands=['send_actual_db'])
def send_actual_db(message):
    if message.from_user.id != admin:
        return
    backupDB()
    predlojka_bot.reply_to(message, "Резервная копия базы данных отправлена!")