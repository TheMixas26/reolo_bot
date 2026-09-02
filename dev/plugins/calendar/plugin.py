from .handlers import register_handlers
from .jobs import check_imperial_events
from .service import calendar
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="Calendar",
        persona="NONE",
        summary="Имперские праздники и календарь",
        tags=("fun", "lore",),
        touches=(
            "пишет в чат каждый день",
            "оповещает о праздниках",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class CalendarPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST
    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(check_imperial_events, 'cron', hour=1, minute=0, misfire_grace_time=7200, args=(context, calendar))

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("calendar", persona="NONE")
        logger.say("It was an template!!..")
        CalendarPlugin.register_jobs(context)
        CalendarPlugin.register_handlers(context)
