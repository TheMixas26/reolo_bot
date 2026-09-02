from .handlers import register_handlers
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="Bank plugin",
        persona="Казначей",
        summary="Буквально банковский плагин",
        tags=("fun", "stats",),
        touches=(
            "своя БД",
            "свой бот",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class BankPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST

    @staticmethod
    def setup(context):
        logger = context.logger_factory("bank", persona="Казначей")
        logger.say("Казначей на месте, к деньгам готов!")

        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        context.ensure_bot("bank", display_name="БАНК")

        predlojka_router, bank_router = register_handlers(context)
        context.include_router("predlojka", predlojka_router)
        context.include_router("bank", bank_router)

        logger.say("Банк подключён: общий predlojka_bot + отдельный bank_bot")
