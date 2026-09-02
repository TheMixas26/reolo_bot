from .handlers import register_handlers
from .jobs import check_achievements
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="achievments",
        persona="Варя",
        summary="Система достижений (WIP)",
        tags=("fun", "stats",),
        touches=(
            "дёргает датабазу",
            "следит за статистикой, чтобы выдавать ачивки",
            "умеет писать в ЛС, если у вас новое достижение"
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class AchievementsPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest = MANIFEST

    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(check_achievements, 'interval', minutes=1, args=(context,))

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("achievements", persona="Варя")
        logger.say("За ачивками слежу!")
        AchievementsPlugin.register_jobs(context)
        AchievementsPlugin.register_handlers(context)
