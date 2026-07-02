from .handlers import register_handlers
from .jobs import send_to_chat

class TemplatePlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(send_to_chat, 'cron', hour=0, minute=0, misfire_grace_time=7200, args=(context,))

    @staticmethod
    def setup(context):
        logger = context.logger_factory("test", persona="Имя")
        logger.say("It was an template!!..")
        TemplatePlugin.register_jobs(context)
        TemplatePlugin.register_handlers(context)
