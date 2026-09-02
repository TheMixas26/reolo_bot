from .jobs import send_weather
from .handlers import register_handlers
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="WeatherPlugin",
        persona="NONE",
        summary="Рассылка погоды",
        tags=("fun",),
        touches=(
            "Пишет в чате",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class WeatherPlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST

    @staticmethod
    def register_jobs(context):

        # Всех с прогнозом погоды!!!! Ура!!!
        context.scheduler.add_job(send_weather, 'cron', hour=12, minute=0, misfire_grace_time=7200, args=(context,))

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        # TODO: имя + фраза сделать
        logger = context.logger_factory("weather", persona="NONE")
        logger.say("phrase")
        WeatherPlugin.register_jobs(context)
        router = register_handlers(context)
        context.include_router("predlojka", router)
