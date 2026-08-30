from .service import send_daily_birthdays, send_personal_birthday_notifications, send_birthday_congratulation
from .handlers import register_handlers

class BirthdaysPlugin:

    @staticmethod
    def register_jobs(context):

        # Отправляем отчёт по др в лс
        context.scheduler.add_job(send_personal_birthday_notifications, 'cron', hour=1, minute=1, misfire_grace_time=7200, args=(context,))

        # Отправляем отчёт по др в группе комментариев
        context.scheduler.add_job(send_daily_birthdays, 'cron', hour=1, minute=0, misfire_grace_time=7200, args=(context,))

        # Поздравляем именинников в лс
        context.scheduler.add_job(send_birthday_congratulation, 'cron', hour=9, minute=30, misfire_grace_time=7200, args=(context,))

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("birthdays", persona="Никитос")
        logger.say("Доброе, выступаю на смену!")
        BirthdaysPlugin.register_jobs(context)
        context.include_router("predlojka", register_handlers(context))
