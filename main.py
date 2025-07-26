from birthdays import send_daily_birthdays
from data import predlojka_bot
from apscheduler.schedulers.background import BackgroundScheduler
import handlers

scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_birthdays, 'cron', hour=1, minute=0, misfire_grace_time=7200)
scheduler.start() 


print("predlojka.py in Предложка Империи succesfully started")

if __name__ == "__main__":
    predlojka_bot.polling(none_stop=True)