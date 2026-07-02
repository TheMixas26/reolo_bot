from .handlers import register_handlers

class BankPlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    # @staticmethod
    # def register_jobs(context):
    #     context.scheduler.add_job(send_to_chat, 'cron', hour=0, minute=0, misfire_grace_time=7200, args=(context,))

    @staticmethod
    def setup(context):
        logger = context.logger_factory("bank", persona="Казначей")
        logger.say("Казначей на месте, к деньгам готов!")
        # BankPlugin.register_jobs(context)
        BankPlugin.register_handlers(context)
