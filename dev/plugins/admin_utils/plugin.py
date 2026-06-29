from .handlers import register_handlers
from .jobs import backupDB
from .service import set_commands

class AdminUtilsPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(backupDB, 'cron', hour=6, minute=0, misfire_grace_time=7200, args=(context,))
        context.scheduler.add_job(backupDB, 'cron', hour=18, minute=0, misfire_grace_time=7200, args=(context,))
        context.scheduler.add_job(set_commands, 'cron', hour=0, minute=0, misfire_grace_time=3600, args=(context,))

    @staticmethod
    def setup(context):
        logger = context.logger_factory("test", persona="Имя")
        logger.say("It was an template!!..")
        AdminUtilsPlugin.register_jobs(context)
        AdminUtilsPlugin.register_handlers(context)
