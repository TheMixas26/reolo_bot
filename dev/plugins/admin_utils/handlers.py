import subprocess

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from .jobs import backupDB
from .service import set_commands
from varibles.dialogue_loader import TEXT
from core.core_plugin.stats import log_command_usage, log_event
from database.sqlite_db import get_all_users


class AdminStates(StatesGroup):
    waiting_for_fake_post = State()
    waiting_for_broadcast = State()


def register_handlers(context) -> Router:
    admin = context.admin_id
    router = Router(name="admin-utils-plugin")

    def _is_admin(message: Message) -> bool:
        return message.from_user.id == admin

    @router.message(Command("fake_post"))
    async def handle_fake_post(message: Message, state: FSMContext):
        if not _is_admin(message):
            return
        log_command_usage("predlojka", "fake_post", message)

        if message.reply_to_message:
            try:
                caption = message.reply_to_message.caption or message.reply_to_message.text or ""
                await message.bot.copy_message(
                    context.channel,
                    message.chat.id,
                    message.reply_to_message.message_id,
                    caption=caption or None,
                )
                await message.reply(TEXT("fakepost", "successfully"))
                log_event(
                    "fake_post_sent",
                    bot="predlojka",
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    metadata={"mode": "reply_copy"},
                )
                return
            except Exception as error:
                await message.reply(f"{TEXT('err', 'message_forward')}{error}")
                return

        await message.reply(TEXT("fakepost", "start"), parse_mode="MarkdownV2")
        await state.set_state(AdminStates.waiting_for_fake_post)

    @router.message(AdminStates.waiting_for_fake_post)
    async def handle_fake_post_text(message: Message, state: FSMContext):
        if not _is_admin(message):
            return
        try:
            await message.bot.send_message(context.channel, message.text)
            await message.answer(TEXT("fakepost", "done"))
            log_event(
                "fake_post_sent",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"mode": "text"},
            )
        except Exception as error:
            await message.answer(f"(╥﹏╥) Ошибка при отправке поста: {error}")
        finally:
            await state.clear()

    @router.message(Command("stop_bot"))
    async def stop_bot(message: Message):
        if not _is_admin(message):
            return
        log_command_usage("predlojka", "stop_bot", message)
        await message.reply(TEXT("stop_bot"))
        await message.answer_photo(FSInputFile("doc/shoot-at-the-server-room-during-the-evacuation.png"))
        raise SystemExit("Бот остановлен администратором")

    @router.message(Command("update_bot"))
    async def update_bot(message: Message):
        if not _is_admin(message):
            return
        log_command_usage("predlojka", "update_bot", message)
        await message.reply(TEXT("update_bot"))
        subprocess.run(["git", "pull"], check=False)
        raise SystemExit("Бот перезапущен администратором")

    @router.message(Command("broadcast"))
    async def public_notify_command(message: Message, state: FSMContext):
        if not _is_admin(message):
            return
        log_command_usage("predlojka", "broadcast", message)
        await message.reply(TEXT("broadcast_start"))
        await state.set_state(AdminStates.waiting_for_broadcast)

    @router.message(AdminStates.waiting_for_broadcast)
    async def handle_public_notify(message: Message, state: FSMContext):
        if not _is_admin(message):
            return
        try:
            users = get_all_users()
            sent_count = 0
            for user in users:
                try:
                    await message.bot.send_message(user["user_id"], message.text)
                    sent_count += 1
                except Exception as error:
                    context.logger.error(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {error}")
            log_event(
                "broadcast_completed",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"sent_count": sent_count},
            )
            await message.reply(TEXT("broadcast_done"))
        except Exception as error:
            await message.reply(f"(╥﹏╥) Ошибка при рассылке: {error}")
        finally:
            await state.clear()

    @router.message(Command("send_actual_db"))
    async def send_actual_db(message: Message):
        if not _is_admin(message):
            return
        log_command_usage("predlojka", "send_actual_db", message)
        await backupDB(context)
        log_event("backup_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)
        await message.reply(TEXT("backup_successfully_send"))

    @router.message(Command("setcmd"))
    async def initial_send_commands(message: Message):
        await set_commands(context, message)

    @router.message(Command("send_smth"))
    async def handle_send_personal_daily(message: Message):
        log_command_usage("predlojka", "send_smth", message)
        if not _is_admin(message):
            return
        command_text = message.text.replace("/send_smth", "").strip()
        try:
            user_id_str, text_to_send = command_text.split("|", 1)
            user_id = int(user_id_str.strip())
            text_to_send = text_to_send.strip()
        except ValueError:
            await message.reply("Ошибка формата. Используйте: /send_smth ID|текст сообщения")
            return
        except Exception as error:
            await message.reply(f"Произошла ошибка: {error}")
            return

        try:
            await message.bot.send_message(user_id, text_to_send)
            await message.reply(f"Сообщение успешно отправлено получателю с ID {user_id}.")
        except Exception as error:
            await message.reply(f"Не удалось отправить сообщение получателю с ID {user_id}. Ошибка: {error}")

    return router
