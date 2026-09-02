from .handlers import register_handlers
from .db import init_cardgame_database
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="Cardgame",
        persona="NONE",
        summary="Карточкая гача",
        tags=("games", "fun",),
        touches=(
            "свой бот",
            "дуэли в чате",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class CardGamePlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST
    
    @staticmethod
    def register_handlers(context):
        register_handlers(context)


    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        context.ensure_bot("rpg", display_name="RPG")
        logger = context.logger_factory("rpg-card", persona="NONE")
        # TODO: назначить персону
        logger.say("Не назначенное имя для карт")
        CardGamePlugin.register_handlers(context)
        init_cardgame_database()
