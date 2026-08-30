from .handlers import register_handlers


class MafiaPlugin:
    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))


    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")


        logger = context.logger_factory("mafia", persona="Крёстный")

        logger.say("Ты приходишь в мой дом, но делаешь это без уважения...")
        router = register_handlers(context)
        context.include_router("predlojka", router)

        

