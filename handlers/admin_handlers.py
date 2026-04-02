from config import predlojka_bot, admin, bank_bot, rpg_bot
from telebot import types
from bank import edit_currency_info
from utils.utils import get_commands_for_set, backupDB
from utils.birthdays import send_daily_birthdays, send_personal_birthday_notifications
from database.sqlite_db import get_all_users
from analytics.stats import log_command_usage, log_event
from posting.models import Platform, PostAuthor, PostOrigin
from posting.runtime import post_publisher, telegram_adapter
from posting.services import PostFactory, PostFormatter

@predlojka_bot.message_handler(commands=['edit_currency'])
def editing_currency(message):
    log_command_usage("predlojka", "edit_currency", message)
    if message.chat.id == admin:
        predlojka_bot.reply_to(message, "Агась! Жду циферки, баты и рубли через запятую.")
        predlojka_bot.register_next_step_handler(message, editing_currency2)
    else:
        predlojka_bot.reply_to(message, "Вы не администратор! Ну-ка перестаньте пытаться сломать экономику!!! (◣_◢)")

def editing_currency2(message):
    try:
        purumpurum = message.text.split(",")
        a = int(purumpurum[0])
        b = int(purumpurum[1])
        edit_currency_info(message, a, b)
    except Exception:
        predlojka_bot.reply_to(message, "Извините, у меня тут не сраслось что-то...")


@predlojka_bot.message_handler(commands=['setcmd'])
def set_commands(message=None):
    if message and message.from_user.id != admin:
        return
    
    scope = types.BotCommandScopeChat(admin)

    predlojka_bot.set_my_commands(get_commands_for_set("predlojka"))
    predlojka_bot.set_my_commands(
        get_commands_for_set("predlojka", include_admin=True),
        scope=scope
    )
    bank_bot.set_my_commands(get_commands_for_set("bank"))
    rpg_bot.set_my_commands(get_commands_for_set("rpg"))
    rpg_bot.set_my_commands(
        get_commands_for_set("rpg", include_admin=True),
        scope=scope,
    )

    if message:
        log_command_usage("predlojka", "setcmd", message)
    log_event("commands_synced", bot="system", metadata={"triggered_by": message.from_user.id if message else "scheduler"})

    if message:
        predlojka_bot.reply_to(message, "Команды обновлены! (⌒_⌒ )")



@predlojka_bot.message_handler(commands=['send_daily'])
def handle_send_daily(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "send_daily", message)
    try:
        send_daily_birthdays()
    except Exception as e:
        print(e)

@predlojka_bot.message_handler(commands=['send_personal_daily'])
def handle_send_personal_daily(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "send_personal_daily", message)
    try:
        send_personal_birthday_notifications()
    except Exception as e:
        print(e)


@predlojka_bot.message_handler(commands=['fake_post'])
def handle_fake_post(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "fake_post", message)

    if message.reply_to_message:
        try:
            post = telegram_adapter.create_raw_post_from_message(message.reply_to_message, append_author_signature=False)
            outcome = post_publisher.publish_post(
                post,
                rendered_text=PostFormatter.compose_publish_text(post),
                disable_notification=True,
            )
            if outcome.has_errors:
                predlojka_bot.reply_to(message, f"Пост отправлен частично. Ошибки: {'; '.join(outcome.errors.values())}")
            else:
                predlojka_bot.reply_to(message, "Готово! Переслала отвеченное сообщение в канал)")
            log_event("fake_post_sent", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"mode": "reply_copy"})
            return
        except Exception as e:
            predlojka_bot.reply_to(message, f"(╥﹏╥) Не получилось переслать сообщение: {e}")
            return

    predlojka_bot.reply_to(message, r"Отлично! Злодействуем значит))) (⌐■‿■)\n\nНапиши пост \(подпись от человека висит на вас\)\n\nНа всякий напоминаю, `👤 {имя}`", parse_mode="MarkdownV2")
    predlojka_bot.register_next_step_handler(message, handle_fake_post2)

def handle_fake_post2(message):
    if message.from_user.id != admin:
        return
    try:
        post = PostFactory.create_raw_post(
            author=PostAuthor(
                user_id=message.from_user.id,
                display_name=telegram_adapter.build_display_name(message.from_user),
                username=getattr(message.from_user, "username", None),
            ),
            origin=PostOrigin(
                platform=Platform.TELEGRAM,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                message_id=message.message_id,
            ),
            text=message.text or "",
            append_author_signature=False,
        )
        outcome = post_publisher.publish_post(
            post,
            rendered_text=PostFormatter.compose_publish_text(post),
            disable_notification=True,
        )
        if outcome.has_errors:
            predlojka_bot.send_message(message.chat.id, f"Пост отправлен частично. Ошибки: {'; '.join(outcome.errors.values())}")
        else:
            predlojka_bot.send_message(message.chat.id, "Готово! Пост улетел. Удачи с махинациями))) (¬‿¬)")
        log_event("fake_post_sent", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"mode": "text"})
    except Exception as e:
        predlojka_bot.send_message(message.chat.id, f"(╥﹏╥) Ошибка при отправке поста: {e}")



@predlojka_bot.message_handler(commands=['stop_bot'])
def stop_bot(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "stop_bot", message)
    predlojka_bot.reply_to(message, "Самоликвидируюсь по приказу командования!!!!!")
    # TODO: пусть скидывает каритнку "при эвакуации выстрелить в серверную"
    SystemExit("Бот остановлен администратором")



@predlojka_bot.message_handler(commands=['broadcast'])
def public_notify_command(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "broadcast", message)
    predlojka_bot.reply_to(message, "Ого! (ノ°ο°)ノ\nУ нас тут рассылка намечается! Напишите сообщение, которое хотите разослать всем пользователям. А остальное оставьте на меня)) (⌐■ω■)")
    predlojka_bot.register_next_step_handler(message, handle_public_notify)


def handle_public_notify(message):
    if message.from_user.id != admin:
        return
    try:
        users = get_all_users()
        sent_count = 0
        for user in users:
            try:
                predlojka_bot.send_message(user['user_id'], message.text)
                sent_count += 1
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
        log_event("broadcast_completed", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"sent_count": sent_count})
        predlojka_bot.reply_to(message, "Рассылка завершена! Надеюсь там не было опечаток... (◠‿◠;;)")
    except Exception as e:
        predlojka_bot.reply_to(message, f"(╥﹏╥) Ошибка при рассылке: {e}")



@predlojka_bot.message_handler(commands=['send_actual_db'])
def send_actual_db(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "send_actual_db", message)
    backupDB()
    log_event("backup_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)
    predlojka_bot.reply_to(message, "Резервная копия базы данных и файлов аналитики отправлена! Люблю свою работу!)) (^-^)")
