from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from varibles import TEXT
from core.core_plugin.stats import log_command_usage, log_event
from .db import get_all_achievements, add_achievement, grant_achievement, revoke_achievement, get_user_achievements, update_achievement
from plugins.bank.db import get_balance


def register_handlers(context) -> Router:
    admin = context.admin_id
    router = Router(name="achievements-plugin")

    @router.message(Command("achievements"))
    async def list_achievements_command(message: Message):
        # TODO: в texts.json
        log_command_usage("predlojka", "achievements", message)
        achievements = await get_all_achievements()
        if not achievements:
            await message.reply(TEXT("empty_achievments_db"))
        else:
            response = TEXT("ach_msg/all/head")
            for ach in achievements:
                response += TEXT("ach_msg/all/body", name=ach['name'], code=ach['code'], desc=ach['description'])
            await message.reply(response)

    @router.message(Command("me"))
    async def get_achievements_command(message: Message):
        log_command_usage("predlojka", "me", message)
        user_id = message.from_user.id
        achievements = await get_user_achievements(user_id)
        balance = await get_balance(user_id)

        if achievements:
            achievements_text = TEXT("ach_msg/me/head")
            for ach in achievements:
                achievements_text += TEXT("ach_msg/me/body", name=ach['name'], desc=ach['description'], obtained_at=ach['obtained_at'])
        else:
            achievements_text = TEXT("no_achievements_yet")

        balance_text = f"\nВаш баланс: {balance}" if balance is not None else "\nВаш баланс пока недоступен."  # TODO: в texts.json
        await message.reply(
            f"Здравствуйте, {message.from_user.first_name}! Рада, что вы заинтересовались собой!)\n\n"    # TODO: в texts.json
            f"{achievements_text}\n\n{balance_text}"
        )

    @router.message(Command("add_achievement"))
    async def add_achievement_command(message: Message):
        if message.from_user.id != admin:
            await message.reply(TEXT("not_an_admin"))
            return
        log_command_usage("predlojka", "add_achievement", message)
        try:
            command, data = message.text.split(" ", 1)
            code, name, description = [x.strip() for x in data.split("|", 2)]
            await add_achievement(code, name, description)
            await message.reply(TEXT("achievement_created").format(name=name, code=code))
            log_event("achievement_created", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"achievement_code": code})
        except ValueError:
            await message.reply(TEXT("err", "wrong_format/add_achievement"))

    @router.message(Command("grant_achievement"))
    async def grant_achievement_command(message: Message):
        if message.from_user.id != admin:
            await message.reply(TEXT("not_an_admin"))
            return
        log_command_usage("predlojka", "grant_achievement", message)
        try:
            command, data = message.text.split(" ", 1)
            user_id_str, achievement_code = [x.strip() for x in data.split("|", 1)]
            user_id = int(user_id_str)
            await grant_achievement(user_id, achievement_code)
            await message.reply(f"Успешно выдала Достижение '{achievement_code}' пользователю {user_id}!")  # TODO: в texts.json
            log_event(
                "achievement_granted_manual",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"target_user_id": user_id, "achievement_code": achievement_code},
            )
        except ValueError:
            await message.reply(TEXT("err", "wrong_format/grant_achievement"))

    @router.message(Command("revoke_achievement"))
    async def revoke_achievement_command(message: Message):
        if message.from_user.id != admin:
            await message.reply(TEXT("not_an_admin"))
            return
        log_command_usage("predlojka", "revoke_achievement", message)
        try:
            command, data = message.text.split(" ", 1)
            user_id_str, achievement_code = [x.strip() for x in data.split("|", 1)]
            user_id = int(user_id_str)
            await revoke_achievement(user_id, achievement_code)
            await message.reply(f"Достижение '{achievement_code}' конфисковано у пользователя {user_id}!)))") # TODO: в texts.json
            log_event(
                "achievement_revoked",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"target_user_id": user_id, "achievement_code": achievement_code},
            )
        except ValueError:
            await message.reply(TEXT("err", "wrong_format/revoke_achievement"))

    @router.message(Command("add_conditions"))
    async def add_conditions_command(message: Message):
        if message.from_user.id != admin:
            await message.reply(TEXT("not_an_admin"))
            return
        log_command_usage("predlojka", "add_conditions", message)
        try:
            command, data = message.text.split(" ", 1)
            achievement_code, conditions = [x.strip() for x in data.split("|", 1)]
            await update_achievement(achievement_code, conditions=conditions)
            await message.reply(f"Обновила условия достижения '{achievement_code}' на '{conditions}'.") # TODO: в texts.json
            log_event(
                "achievement_conditions_updated",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"achievement_code": achievement_code},
            )
        except ValueError:
            await message.reply(TEXT("err", "wrong_format/add_conditions"))

    return router
