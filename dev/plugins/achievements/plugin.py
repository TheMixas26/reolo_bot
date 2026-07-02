from .handlers import register_handlers
from .jobs import check_achievements

class AchievementsPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(check_achievements, 'interval', minutes=1, args=(context,))

    @staticmethod
    def setup(context):
        logger = context.logger_factory("achievements", persona="Варя")
        logger.say("За ачивками слежу!")
        AchievementsPlugin.register_jobs(context)
        AchievementsPlugin.register_handlers(context)
