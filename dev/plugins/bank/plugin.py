from .handlers import register_handlers


class BankPlugin:
    name = "bank"

    @staticmethod
    def setup(context):
        logger = context.logger_factory("bank", persona="Казначей")
        logger.say("Казначей на месте, к деньгам готов!")

        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        context.ensure_bot("bank", display_name="БАНК")

        predlojka_router, bank_router = register_handlers(context)
        context.include_router("predlojka", predlojka_router)
        context.include_router("bank", bank_router)

        logger.say("Банк подключён: общий predlojka_bot + отдельный bank_bot")
