from birthdays import send_daily_birthdays
from data import predlojka_bot
from apscheduler.schedulers.background import BackgroundScheduler
import handlers
import logging
import time

logging.basicConfig(
    filename='bot_errors.log',
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s %(message)s'
)

scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_birthdays, 'cron', hour=1, minute=0, misfire_grace_time=7200)
scheduler.start() 

if __name__ == "__main__":
    while True:
        try:
            print("predlojka.py in Предложка Империи succesfully started")
            predlojka_bot.polling(none_stop=True)
        except Exception as e:
            logging.error("Ошибка в работе бота", exc_info=True)
            print(f"Произошла ошибка: {e}. Перезапуск через 10 секунд...")
            time.sleep(10)