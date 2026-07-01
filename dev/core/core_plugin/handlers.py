from varibles.dialogue_loader import TEXT
from settings import PROJECT_NAME, render_text_template
from analytics.stats import log_command_usage, log_event
from database.sqlite_db import user_exists, create_user_if_missing
from .service import get_changelog


def register_handlers(context):
    predlojka_telegram_adapter = context.tg_adapter
    bot = context.predlojka_bot
    logger = context.logger

    def start(message):
        log_command_usage("predlojka", "start", message)
        if user_exists(message.from_user.id):
            predlojka_telegram_adapter.reply_to(message, text=f"С возвращением!!! Ожидаем постов)")
        else:
            create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
            predlojka_telegram_adapter.reply_to(message, text=f"Добро пожаловать в бота \"{PROJECT_NAME}!\"")
            # TODO: нормальное привествие новых пользователей
            log_event("user_registered", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)

    def changelog(message):
        file_path, bot_version = get_changelog()
        log_command_usage("predlojka", "changelog", message)

        if file_path is not None:
            with open(file_path) as file:
                predlojka_telegram_adapter.send_document(
                    message.chat.id, file,
                    reply_to_message_id=message.message_id,
                    caption=TEXT("changelog_command", bot_version=bot_version),
                    parse_mode='HTML'
                )
        else:
            predlojka_telegram_adapter.reply_to(
            message,
            text=TEXT("err", "changelog_command")
        )
            logger.error(bot_version)


    def help(message):
        log_command_usage("predlojka", "help", message)
        try:
            help_string = render_text_template(TEXT("help_info"))
            predlojka_telegram_adapter.reply_to(message, text=help_string, parse_mode='HTML')
        except Exception as e:
            logger.error(e)
            predlojka_telegram_adapter.reply_to(
                message,
                text=TEXT("err", "help_command")
            )




    bot.register_message_handler(
        start,
        commands=['start']
    )

    bot.register_message_handler(
        changelog,
        commands=['changelog']
    )

    bot.register_message_handler(
        help,
        commands=['help']
    )