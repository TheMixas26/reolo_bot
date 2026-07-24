from .handlers import register_handlers
from .jobs import publish_due_scheduled_posts


class PredlojkaPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def register_jobs(context):
        if context.scheduler.get_job("publish_scheduled_posts") is not None:
            return
        context.scheduler.add_job(
            publish_due_scheduled_posts,
            "interval",
            minutes=1,
            id="publish_scheduled_posts",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("predlojka", persona="Варя")
        logger.say("Плагин предложки подключён.")
        PredlojkaPlugin.register_jobs(context)
        PredlojkaPlugin.register_handlers(context)
