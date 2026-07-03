from core.core_plugin.stats import log_command_usage
from .jobs import send_weather
from varibles.dialogue_loader import TEXT


def register_handlers(context):
    admin = context.admin_id
    bot = context.predlojka_bot


    def command_to_send_weather(message):
        if message.from_user.id != admin:
            return
        log_command_usage("predlojka", "send_weather", message)
        send_weather(context)
        bot.reply_to(message, TEXT("forced_weather"))



    bot.register_message_handler(
        command_to_send_weather,
        commands=['send_weather']
    )