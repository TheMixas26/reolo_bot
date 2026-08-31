from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from varibles import TEXT
from settings import PROJECT_NAME, render_text_template
from core.core_plugin.stats import log_command_usage, log_event
from database.sqlite_db import user_exists, create_user_if_missing
from .service import get_changelog


def register_handlers(context) -> Router:
    router = Router(name="core-plugin")
    logger = context.logger

    @router.message(Command("start"))
    async def start(message: Message):
        log_command_usage("predlojka", "start", message)
        if await user_exists(message.from_user.id):
            await message.reply(text="С возвращением!!! Ожидаем постов)")
        else:
            await create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
            await message.reply(text=f"Добро пожаловать в бота \"{PROJECT_NAME}!\"")
            log_event("user_registered", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)

    @router.message(Command("changelog"))
    async def changelog(message: Message):
        file_path, bot_version = get_changelog()
        log_command_usage("predlojka", "changelog", message)

        if file_path is not None:
            await message.answer_document(
                FSInputFile(file_path),
                caption=TEXT("changelog_command", bot_version=bot_version),
                parse_mode="HTML",
            )
        else:
            await message.reply(text=TEXT("err", "changelog_command"))
            logger.error(bot_version)

    @router.message(Command("help"))
    async def help_command(message: Message):
        log_command_usage("predlojka", "help", message)
        try:
            help_string = render_text_template(TEXT("help_info"))
            await message.reply(text=help_string, parse_mode="HTML")
        except Exception as error:
            logger.error(error)
            await message.reply(text=TEXT("err", "help_command"))

    return router
