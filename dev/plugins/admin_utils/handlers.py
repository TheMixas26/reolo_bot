from .jobs import backupDB
from .service import set_commands
from varibles.dialogue_loader import TEXT
from telebot import types
from core.core_plugin.stats import log_command_usage, log_event
import subprocess
from database.sqlite_db import get_all_users

def register_handlers(context):
    admin = context.admin_id
    bot = context.predlojka_bot


    def handle_fake_post(context, message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "fake_post", message)

        if message.reply_to_message:
            try:
                caption = message.reply_to_message.caption or message.reply_to_message.text or ""
                if caption:
                    bot.copy_message(context.channel, message.chat.id, message.reply_to_message.message_id, caption=caption)
                else:
                    bot.copy_message(context.channel, message.chat.id, message.reply_to_message.message_id)
                bot.reply_to(message, TEXT("fakepost", "successfully"))
                log_event("fake_post_sent", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"mode": "reply_copy"})
                return
            except Exception as e:
                bot.reply_to(message, f"{TEXT("err", "message_forward")}{e}")
                return

        bot.reply_to(message, TEXT("fakepost", "start"), parse_mode="MarkdownV2")
        bot.register_next_step_handler(message, handle_fake_post2(context))

    def handle_fake_post2(context, message):
        if message.from_user.id != admin:
            return
        try:
            bot.send_message(context.channel, message.text)
            bot.send_message(message.chat.id, TEXT("fakepost", "done"))
            log_event("fake_post_sent", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"mode": "text"})
        except Exception as e:
            bot.send_message(message.chat.id, f"(╥﹏╥) Ошибка при отправке поста: {e}")

    def stop_bot(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "stop_bot", message)
        bot.reply_to(message, TEXT("stop_bot"))
        with open('doc/shoot-at-the-server-room-during-the-evacuation.png', 'rb') as photo:
            bot.send_photo(message.chat.id, photo)
        SystemExit("Бот остановлен администратором")

    def update_bot(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "update_bot", message)
        bot.reply_to(message, TEXT('update_bot'))
        subprocess.run(['git', 'pull'])
        SystemExit("Бот перезапущен администратором")

    def public_notify_command(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "broadcast", message)
        bot.reply_to(message, TEXT("broadcast_start"))
        bot.register_next_step_handler(message, handle_public_notify)


    def handle_public_notify(message):
        if message.from_user.id != admin:
            return
        try:
            users = get_all_users()
            sent_count = 0
            for user in users:
                try:
                    bot.send_message(user['user_id'], message.text)
                    sent_count += 1
                except Exception as e:
                    context.logger.error(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
            log_event("broadcast_completed", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"sent_count": sent_count})
            bot.reply_to(message, TEXT("broadcast_done"))
        except Exception as e:
            bot.reply_to(message, f"(╥﹏╥) Ошибка при рассылке: {e}")

    def send_actual_db(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "send_actual_db", message)
        backupDB()
        log_event("backup_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)
        bot.reply_to(message, TEXT('backup_successfully_send'))

    def initial_send_commands(message):
        set_commands(context, message)

    def handle_send_personal_daily(message):
        log_command_usage("predlojka", "send_smth", message)
        if message.from_user.id != admin:
            return
        command_text = message.text.replace('/send_smth', '').strip()

        try:
            user_id_str, text_to_send = command_text.split('|', 1)  
            user_id = int(user_id_str.strip())
            text_to_send = text_to_send.strip()
        except ValueError:
            bot.reply_to(message, "Ошибка формата. Используйте: /send_smth ID|текст сообщения")
            return
        except Exception as e:
            bot.reply_to(message, f"Произошла ошибка: {e}")
            return

        try:
            bot.send_message(user_id, text_to_send)
            bot.reply_to(
                message,
                f"Сообщение успешно отправлено получателю с ID {user_id}."
            )
        except Exception as e:
        
            bot.reply_to(
                message,
                f"Не удалось отправить сообщение получателю с ID {user_id}. Ошибка: {e}"
            )




    bot.register_message_handler(
        initial_send_commands,
        commands=['setcmd']
    )
    bot.register_message_handler(
        handle_fake_post,
        commands=['fake_post']
    )
    bot.register_message_handler(
        stop_bot,
        commands=['stop_bot']
    )
    bot.register_message_handler(
        update_bot,
        commands=['update_bot']
    )
    bot.register_message_handler(
        public_notify_command,
        commands=['broadcast']
    )
    bot.register_message_handler(
        send_actual_db,
        commands=['send_actual_db']
    )

    bot.register_message_handler(
        handle_send_personal_daily,
        commands=['send_smth']
    )

        