from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.core_plugin.stats import log_command_usage, log_event
from varibles.dialogue_loader import TEXT
from .service import (
    add_birthday,
    add_birthday_by_username,
    change_personal_notify,
    get_user_birthday,
    send_daily_birthdays,
    send_personal_birthday_notifications,
)


def register_handlers(context) -> Router:
    logger = context.logger_factory("birthdays", persona="Никитос")
    admin = context.admin_id
    router = Router(name="birthdays-plugin")

    logger.say("От имени плагина дней рождений регестрирую команды...")

    @router.message(Command("add_birthday_by_username"))
    async def handle_add_birthday_by_username(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "add_birthday_by_username", message)
        try:
            parts = message.text.split()
            if message.reply_to_message:
                if len(parts) != 2:
                    await message.reply("Формат в reply: /add_birthday_by_username ДД.ММ")
                    return
                target = message.reply_to_message.from_user
                date_str = parts[1]
                name = f"{target.first_name or ''} {target.last_name or ''}".strip()
                ok = add_birthday(context, target.id, name, date_str)
                if ok:
                    await message.reply(f"День рождения для {name} добавлен!")
                    log_event(
                        "birthday_added_admin",
                        bot="predlojka",
                        user_id=message.from_user.id,
                        chat_id=message.chat.id,
                        metadata={"target_user_id": target.id, "mode": "reply"},
                    )
                else:
                    await message.reply("Ошибка при добавлении. Вероятно, дело в дате!")
                return

            if len(parts) < 3:
                await message.reply("Формат: /add_birthday_by_username username ДД.ММ")
                return
            username = parts[1].lstrip("@")
            date_str = parts[2]
            chat_id = context.config.chat_mishas_den
            ok, name = await add_birthday_by_username(context, username, date_str, chat_id)
            if ok:
                await message.reply(f"День рождения для {name} добавлен!")
                log_event(
                    "birthday_added_admin",
                    bot="predlojka",
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    metadata={"target_username": username, "mode": "username"},
                )
            else:
                await message.reply(TEXT("err", "bday_adding"))
        except Exception as error:
            await message.reply(f"Ошибка: {error}")

    @router.message(Command("add_birthday"))
    async def handle_add_birthday(message: Message):
        log_command_usage("predlojka", "add_birthday", message)
        try:
            parts = message.text.split()
            if len(parts) != 2:
                await message.reply("Формат: /add_birthday ДД.ММ или /add_birthday ДД.ММ.ГГГГ")
                return
            date_str = parts[1]
            user_id = message.from_user.id
            name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
            ok = add_birthday(context, user_id, name, date_str)
            if ok:
                await message.reply("Ваш день рождения успешно добавлен!")
                log_event("birthday_added_user", bot="predlojka", user_id=user_id, chat_id=message.chat.id)
            else:
                await message.reply(TEXT("err", "check_date_format"))
        except Exception as error:
            await message.reply(f"Ошибка: {error}")

    @router.message(Command("personal_notifications"))
    async def handle_personal_notifications(message: Message):
        log_command_usage("predlojka", "personal_notifications", message)
        user_id = message.from_user.id
        user = get_user_birthday(user_id)
        if user:
            current = user.get("personal_notify", False)
            change_personal_notify(user_id, not current)
            log_event(
                "birthday_personal_notifications_toggled",
                bot="predlojka",
                user_id=user_id,
                chat_id=message.chat.id,
                metadata={"enabled": not current},
            )
            await message.reply(TEXT("personal_bday_enabled") if not current else TEXT("personal_bday_disabled"))
        else:
            await message.reply(TEXT("add_bday_before"))

    @router.message(Command("send_personal_daily"))
    async def handle_send_personal_daily(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "send_personal_daily", message)
        try:
            await send_personal_birthday_notifications(context)
        except Exception as error:
            logger.say(error, "error")

    @router.message(Command("send_daily"))
    async def handle_send_daily(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "send_daily", message)
        try:
            await send_daily_birthdays(context)
        except Exception as error:
            logger.say(error, "error")

    logger.say("Все команды добавлены!")
    return router
