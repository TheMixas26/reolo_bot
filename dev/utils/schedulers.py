from handlers.predlojka_handlers import publish_due_scheduled_posts
from apscheduler.schedulers.background import BackgroundScheduler
from utils.weather import send_weather
from utils.utils import backupDB, bot_reboot
from utils.imperial_сalender import check_imperial_events
from achievements.achievement_system import check_achievements
from handlers.admin_handlers import set_commands

scheduler = BackgroundScheduler()

def start_scheduler() -> None:
    """Запуск всех фоновых процессов"""
    # Проверяем имперские события и отправляем отчёт в группу комментариев
    scheduler.add_job(check_imperial_events, 'cron', hour=1, minute=0, misfire_grace_time=7200)

    # Всех с прогнозом погоды!!!! Ура!!!
    scheduler.add_job(send_weather, 'cron', hour=12, minute=0, misfire_grace_time=7200)

    # На всякий случай бэкап в 6 утра
    scheduler.add_job(backupDB, 'cron', hour=6, minute=0, misfire_grace_time=7200)

    # На всякий случай бэкап в 6 вечера
    scheduler.add_job(backupDB, 'cron', hour=18, minute=0, misfire_grace_time=7200)

    # Проверяем достижения
    scheduler.add_job(check_achievements, 'interval', minutes=1)

    # Планово ребутимся
    # scheduler.add_job(bot_reboot, 'cron', hour=0, minute=0, misfire_grace_time=3600)

    # Обновляем команды бота в телеграме раз в день, ну так, чисто на случай
    scheduler.add_job(set_commands, 'cron', hour=0, minute=0, misfire_grace_time=3600)

    # Публикуем запланированные посты каждую минуту
    scheduler.add_job(publish_due_scheduled_posts,"interval", minutes=1, id="publish_scheduled_posts", max_instances=1, coalesce=True, misfire_grace_time=120)

    scheduler.start()