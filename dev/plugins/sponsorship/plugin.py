from .handlers import register_handlers

class SponsorshipPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def setup(context):
        logger = context.logger_factory("sponsorship", persona="Партнёрская программа Вари")
        logger.say("Плагин спонсорки запущен")
        TemplatePlugin.register_handlers(context)
