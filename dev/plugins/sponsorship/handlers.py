from .jobs import send_to_chat
from varibles.dialogue_loader import TEXT


def register_handlers(context):
    predlojka_telegram_adapter = context.tg_adapter
    admin = context.admin_id
    bot = context.predlojka_bot


    def allied_channels(message):
        predlojka_telegram_adapter.reply_to(message, TEXT("allied_channels"))



    bot.register_message_handler(
        allied_channels,
        commands=['allies']
    )
