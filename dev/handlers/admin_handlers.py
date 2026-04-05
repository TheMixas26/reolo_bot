from config import predlojka_bot, admin, channel, bank_bot, rpg_bot
from telebot import types
from bank import edit_currency_info
from utils.utils import get_commands_for_set, backupDB
from utils.birthdays import send_daily_birthdays, send_personal_birthday_notifications
from database.scheduled_posts_db import list_scheduled_posts
from database.sqlite_db import get_all_users
from analytics.stats import log_command_usage, log_event
from posting.runtime import predlojka_telegram_adapter


def _preview_scheduled_payload(payload: dict, content_type: str) -> str:
    if content_type == "album":
        media = payload.get("media") or []
        first_caption = ""
        if media:
            first_caption = (media[0].get("caption") or "").strip()
        snippet = first_caption or f"Альбом из {len(media)} элементов"
    else:
        snippet = (payload.get("publish_text") or "").strip()

    snippet = snippet.replace("\n", " ")
    if len(snippet) > 90:
        snippet = snippet[:87] + "..."
    return snippet or "(без текста)"


@predlojka_bot.message_handler(commands=['drafts', 'scheduled_posts'])
def show_scheduled_posts(message):
    if message.from_user.id != admin:
        return

    log_command_usage("predlojka", "scheduled_posts", message)
    rows = list_scheduled_posts(limit=30)

    if not rows:
        predlojka_telegram_adapter.reply_to(message, "В `scheduled_posts` пока пусто: ни черновиков, ни отложек нет.", parse_mode="Markdown")
        return

    lines = ["Содержимое `scheduled_posts`:\n"]
    for row in rows:
        status_label = "Запланировано" if row["status"] == "scheduled" else "Черновик"
        publish_at = row.get("publish_at") or "без даты"
        content_type = row.get("content_type") or "unknown"
        source_user_id = row.get("source_user_id")
        preview = _preview_scheduled_payload(row.get("payload") or {}, content_type)
        lines.append(
            f"#{row['doc_id']} | {status_label} | {content_type} | {publish_at} | user {source_user_id}\n{preview}\n"
        )

    predlojka_telegram_adapter.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@predlojka_bot.message_handler(commands=['edit_currency'])
def editing_currency(message):
    log_command_usage("predlojka", "edit_currency", message)
    if message.chat.id == admin:
        predlojka_telegram_adapter.reply_to(message, "Агась! Жду циферки, баты и рубли через запятую.")
        predlojka_bot.register_next_step_handler(message, editing_currency2)
    else:
        predlojka_telegram_adapter.reply_to(message, "Вы не администратор! Ну-ка перестаньте пытаться сломать экономику!!! (◣_◢)")

def editing_currency2(message):
    try:
        purumpurum = message.text.split(",")
        a = int(purumpurum[0])
        b = int(purumpurum[1])
        edit_currency_info(message, a, b)
    except Exception:
        predlojka_telegram_adapter.reply_to(message, "Извините, у меня тут не сраслось что-то...")


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
        predlojka_telegram_adapter.reply_to(message, "Команды обновлены! (⌒_⌒ )")



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
            caption = message.reply_to_message.caption or message.reply_to_message.text or ""
            if caption:
                predlojka_telegram_adapter.copy_message(channel, message.chat.id, message.reply_to_message.message_id, caption=caption)
            else:
                predlojka_telegram_adapter.copy_message(channel, message.chat.id, message.reply_to_message.message_id)
            predlojka_telegram_adapter.reply_to(message, "Готово! Переслала отвеченное сообщение в канал)")
            log_event("fake_post_sent", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"mode": "reply_copy"})
            return
        except Exception as e:
            predlojka_telegram_adapter.reply_to(message, f"(╥﹏╥) Не получилось переслать сообщение: {e}")
            return

    predlojka_telegram_adapter.reply_to(message, r"Отлично! Злодействуем значит))) (⌐■‿■)\n\nНапиши пост \(подпись от человека висит на вас\)\n\nНа всякий напоминаю, `👤 {имя}`", parse_mode="MarkdownV2")
    predlojka_bot.register_next_step_handler(message, handle_fake_post2)

def handle_fake_post2(message):
    if message.from_user.id != admin:
        return
    try:
        predlojka_telegram_adapter.send_message(channel, message.text)
        predlojka_telegram_adapter.send_message(message.chat.id, "Готово! Пост улетел. Удачи с махинациями))) (¬‿¬)")
        log_event("fake_post_sent", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"mode": "text"})
    except Exception as e:
        predlojka_telegram_adapter.send_message(message.chat.id, f"(╥﹏╥) Ошибка при отправке поста: {e}")



@predlojka_bot.message_handler(commands=['stop_bot'])
def stop_bot(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "stop_bot", message)
    predlojka_telegram_adapter.reply_to(message, "Самоликвидируюсь по приказу командования!!!!!")
    # TODO: пусть скидывает каритнку "при эвакуации выстрелить в серверную"
    SystemExit("Бот остановлен администратором")



@predlojka_bot.message_handler(commands=['broadcast'])
def public_notify_command(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "broadcast", message)
    predlojka_telegram_adapter.reply_to(message, "Ого! (ノ°ο°)ノ\nУ нас тут рассылка намечается! Напишите сообщение, которое хотите разослать всем пользователям. А остальное оставьте на меня)) (⌐■ω■)")
    predlojka_bot.register_next_step_handler(message, handle_public_notify)


def handle_public_notify(message):
    if message.from_user.id != admin:
        return
    try:
        users = get_all_users()
        sent_count = 0
        for user in users:
            try:
                predlojka_telegram_adapter.send_message(user['user_id'], message.text)
                sent_count += 1
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
        log_event("broadcast_completed", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"sent_count": sent_count})
        predlojka_telegram_adapter.reply_to(message, "Рассылка завершена! Надеюсь там не было опечаток... (◠‿◠;;)")
    except Exception as e:
        predlojka_telegram_adapter.reply_to(message, f"(╥﹏╥) Ошибка при рассылке: {e}")



@predlojka_bot.message_handler(commands=['send_actual_db'])
def send_actual_db(message):
    if message.from_user.id != admin:
        return
    log_command_usage("predlojka", "send_actual_db", message)
    backupDB()
    log_event("backup_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)
    predlojka_telegram_adapter.reply_to(message, "Резервная копия базы данных и файлов аналитики отправлена! Люблю свою работу!)) (^-^)")
