from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from varibles.dialogue_loader import TEXT
from core.core_plugin.stats import log_command_usage, log_event
from .db import get_all_achievements, add_achievement, grant_achievement, revoke_achievement, get_user_achievements, update_achievement
from plugins.bank.db import get_balance


def register_handlers(context) -> Router:
    admin = context.admin_id
    router = Router(name="achievements-plugin")

    @router.message(Command("achievements"))
    async def list_achievements_command(message: Message):
        log_command_usage("predlojka", "achievements", message)
        achievements = get_all_achievements()
        if not achievements:
            await message.reply("Пока что никаких достижений нет. (;￣▽￣)")
        else:
            response = "А вот и все доступные вам достижения:\n"
            for ach in achievements:
                response += f"- {ach['name']} (код: {ach['code']}): {ach['description']}\n"
            await message.reply(response)

    @router.message(Command("me"))
    async def get_achievements_command(message: Message):
        log_command_usage("predlojka", "me", message)
        user_id = message.from_user.id
        achievements = get_user_achievements(user_id)
        balance = get_balance(user_id)

        if achievements:
            achievements_text = "Ваши достижения:\n"
            for ach in achievements:
                achievements_text += f"- {ach['name']}: {ach['description']} (получено: {ach['obtained_at']})\n"
        else:
            achievements_text = TEXT("no_achievements_yet")

        balance_text = f"\nВаш баланс: {balance}" if balance is not None else "\nВаш баланс пока недоступен."
        await message.reply(
            f"Здравствуйте, {message.from_user.first_name}! Рада, что вы заинтересовались собой!)\n\n"
            f"{achievements_text}\n\n{balance_text}"
        )

    @router.message(Command("add_achievement"))
    async def add_achievement_command(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "add_achievement", message)
        try:
            command, data = message.text.split(" ", 1)
            code, name, description = [x.strip() for x in data.split("|", 2)]
            add_achievement(code, name, description)
            await message.reply(TEXT("achievement_created").format(name=name, code=code))
            log_event("achievement_created", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"achievement_code": code})
        except ValueError:
            await message.reply("Формат:\n/add_achievement code | name | description")

    @router.message(Command("grant_achievement"))
    async def grant_achievement_command(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "grant_achievement", message)
        try:
            command, data = message.text.split(" ", 1)
            user_id_str, achievement_code = [x.strip() for x in data.split("|", 1)]
            user_id = int(user_id_str)
            grant_achievement(user_id, achievement_code)
            await message.reply(f"Успешно выдала Достижение '{achievement_code}' пользователю {user_id}!")
            log_event(
                "achievement_granted_manual",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"target_user_id": user_id, "achievement_code": achievement_code},
            )
        except ValueError:
            await message.reply("Формат:\n/grant_achievement user_id | achievement_code")

    @router.message(Command("revoke_achievement"))
    async def revoke_achievement_command(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "revoke_achievement", message)
        try:
            command, data = message.text.split(" ", 1)
            user_id_str, achievement_code = [x.strip() for x in data.split("|", 1)]
            user_id = int(user_id_str)
            revoke_achievement(user_id, achievement_code)
            await message.reply(f"Достижение '{achievement_code}' конфисковано у пользователя {user_id}!)))")
            log_event(
                "achievement_revoked",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"target_user_id": user_id, "achievement_code": achievement_code},
            )
        except ValueError:
            await message.reply("Формат:\n/revoke_achievement user_id | achievement_code")

    @router.message(Command("add_conditions"))
    async def add_conditions_command(message: Message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "add_conditions", message)
        try:
            command, data = message.text.split(" ", 1)
            achievement_code, conditions = [x.strip() for x in data.split("|", 1)]
            update_achievement(achievement_code, conditions=conditions)
            await message.reply(f"Обновила условия достижения '{achievement_code}' на '{conditions}'.")
            log_event(
                "achievement_conditions_updated",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"achievement_code": achievement_code},
            )
        except ValueError:
            await message.reply("Формат:\n/add_conditions achievement_code | conditions")

    return router
