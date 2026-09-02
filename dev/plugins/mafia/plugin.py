from core.manifest import PluginManifest, register_manifest
from .handlers import register_handlers

MANIFEST = register_manifest(PluginManifest(
        name="mafia",
        persona="Крёстный",
        summary="Игра в Мафию для chat_mishas_den",
        tags=("games",),
        touches=(
            "эфимерные сообщения",
            "занимает чат таймерами на всю партию",
            # smth else...
        ),
        permission="public",
        monopoly=True,
    ))

class MafiaPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest = MANIFEST

    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))


    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")


        logger = context.logger_factory("mafia", persona="Крёстный")

        logger.say("Ты приходишь в мой дом, но делаешь это без уважения...")
        router = register_handlers(context)
        context.include_router("predlojka", router)



