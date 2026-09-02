from .handlers import register_handlers
from .jobs import backupDB
from .service import set_commands
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="admin utilities",
        persona="Варя",
        summary="Админские шутчки-дрючки",
        tags=("moderation", "admin",),
        touches=(
            "бэкапы",
            "перезапуски и обновления бота",
            "особые админские команды",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class AdminUtilsPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST
    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(backupDB, 'cron', hour=6, minute=0, misfire_grace_time=7200, args=(context,))
        context.scheduler.add_job(backupDB, 'cron', hour=18, minute=0, misfire_grace_time=7200, args=(context,))
        context.scheduler.add_job(set_commands, 'cron', hour=0, minute=0, misfire_grace_time=3600, args=(context,))

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("admin_utils", persona="Варя")
        logger.say("Админские штучки-дрючки присоеденены!")
        AdminUtilsPlugin.register_jobs(context)
        AdminUtilsPlugin.register_handlers(context)
