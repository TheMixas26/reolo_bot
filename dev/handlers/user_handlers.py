from config import predlojka_bot
from analytics.stats import log_command_usage
from posting.runtime import predlojka_telegram_adapter
from settings import RPG_BOT_NAME, RPG_BOT_USERNAME

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



