from config import predlojka_bot
from database.sqlite_db import user_exists, create_user_if_missing
from analytics.stats import log_command_usage, log_event
from posting.runtime import predlojka_telegram_adapter
from settings import MAIN_BOT_NAME, PROJECT_NAME, RPG_BOT_NAME, RPG_BOT_USERNAME, render_text_template
from varibles.dialogue_loader import TEXT
import logging

logger = logging.getLogger(__name__)

@predlojka_bot.message_handler(commands=['start'])
def start(message):
    log_command_usage("predlojka", "start", message)
    if user_exists(message.from_user.id):
        predlojka_telegram_adapter.reply_to(message, text=f"С возвращением!!! Ожидаем постов)")
    else:
        create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)
        predlojka_telegram_adapter.reply_to(message, text=f"Добро пожаловать в бота \"{PROJECT_NAME}!\"")
        # TODO: нормальное привествие новых пользователей
        log_event("user_registered", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)



@predlojka_bot.message_handler(commands=['changelog'])
def changelog(message):
    log_command_usage("predlojka", "changelog", message)
    build = None
    name = None

    try:
        with open('dev/varibles/changelog.txt', mode='r', encoding='utf-8') as f:
            for line in f:
                if "BUILD" in line and build is None:
                    build = line.split("BUILD")[1].strip(" | \n")
                if "NAME" in line and name is None:
                    name = line.split("NAME")[1].strip(" | \n")

                if build and name:
                    break

            bot_version = f"{build} - {name}"

        with open('dev/varibles/changelog.txt', mode='r', encoding='utf-8') as f:
            predlojka_telegram_adapter.send_document(
                message.chat.id, f,
                reply_to_message_id=message.message_id,
                caption=TEXT("changelog_command", bot_version=bot_version),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(e)
        predlojka_telegram_adapter.reply_to(
            message,
            text=TEXT("err", "changelog_command")
        )






@predlojka_bot.message_handler(commands=['help'])
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



@predlojka_bot.message_handler(commands=['battle'])
def redirect_to_rpg_bot(message):
    log_command_usage("predlojka", "battle", message)
    predlojka_telegram_adapter.reply_to(
        message,
        # TODO: перенести в texts.json
        f"Притормози, дружище! Вся RPG система переехала в {RPG_BOT_NAME}. "
        f"Не волнуйся, формально это всё ещё я, просто вынесенная часть проекта. "
        f"Бегом в него!\n\n{RPG_BOT_USERNAME}"
    )



