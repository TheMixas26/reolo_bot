from .handlers import register_handlers


class AIPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def register_jobs(context):
        pass

    @staticmethod
    def setup(context):
        logger = context.logger_factory("ai", persona="Борман")
        logger.say("Доброе, выступаю на смену!")
        AIPlugin.register_jobs(context)
        AIPlugin.register_handlers(context)
