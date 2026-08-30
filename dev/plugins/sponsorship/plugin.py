from .handlers import register_handlers

class SponsorshipPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("sponsorship", persona="Партнёрская программа Вари")
        logger.say("Плагин спонсорки запущен")
        context.include_router("predlojka", register_handlers(context))