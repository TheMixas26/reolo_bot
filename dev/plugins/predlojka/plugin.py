from .handlers import publish_due_scheduled_posts, register_handlers


class PredlojkaPlugin:
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
        logger = context.logger_factory("predlojka", persona="Варя")
        logger.say("Плагин предложки подключён.")
        register_handlers(context)
        PredlojkaPlugin.register_jobs(context)
