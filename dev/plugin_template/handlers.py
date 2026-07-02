from .jobs import send_to_chat
from varibles.dialogue_loader import TEXT


def register_handlers(context):
    predlojka_telegram_adapter = context.tg_adapter
    admin = context.admin_id
    bot = context.predlojka_bot


    def command_to_send_to_chat(message):
        if message.from_user.id != admin:
            return
        send_to_chat(context)
        predlojka_telegram_adapter.reply_to(message, TEXT("testing_text"))



    bot.register_message_handler(
        command_to_send_to_chat,
        commands=['ur_command']
    )