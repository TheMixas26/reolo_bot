from .handlers import register_handlers
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="Sponsorship",
        persona="Варя?..",
        summary="Партнёрская программа Вари",
        tags=("official",),
        touches=(
            "только смски в ответ на команду (пока что)",
        ),
        permission="public",
        monopoly=False,
    ))

class SponsorshipPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("sponsorship", persona="Партнёрская программа Вари")
        logger.say("Плагин спонсорки запущен")
        context.include_router("predlojka", register_handlers(context))
