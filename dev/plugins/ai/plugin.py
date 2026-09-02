from .handlers import register_handlers
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="AI Plugin",
        persona="Борман",
        summary="Генерация ИИ ответов",
        tags=("moderation", "admin",),
        touches=(
            "основной хендлер предложки",
            "свои теги (#ai)",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class AIPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def register_jobs(context):
        pass

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("ai", persona="Борман")
        logger.say("Доброе, выступаю на смену!")
        AIPlugin.register_jobs(context)
        AIPlugin.register_handlers(context)
