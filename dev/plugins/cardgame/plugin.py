from .handlers import register_handlers
from .db import init_cardgame_database

class CardGamePlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)


    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        context.ensure_bot("rpg", display_name="RPG")
        logger = context.logger_factory("rpg-card", persona="Имя")
        logger.say("Не назначенное имя для карт")
        CardGamePlugin.register_handlers(context)
        init_cardgame_database()
