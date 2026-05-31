from .jobs import send_weather
from .handlers import register_handlers

class WeatherPlugin:

    @staticmethod
    def register_jobs(context):

        # Всех с прогнозом погоды!!!! Ура!!!
        context.scheduler.add_job(send_weather, 'cron', hour=12, minute=0, misfire_grace_time=7200, args=(context,))

    @staticmethod
    def setup(context):
        logger = context.logger_factory("birthdays", persona="Никитос")
        logger.say("Доброе, выступаю на смену!")
        WeatherPlugin.register_jobs(context)
        register_handlers(context)