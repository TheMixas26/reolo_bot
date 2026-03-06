from utils.birthdays import send_daily_birthdays, send_personal_birthday_notifications
from apscheduler.schedulers.background import BackgroundScheduler
from handlers import user_handlers, admin_handlers, misc_handlers, achievements_handlers, predlojka_handlers, bank_handlers, rpg_handlers
import logging
from threading import Thread
import time
from utils.weather import send_weather
from utils.utils import backupBD
try:
    from config import predlojka_bot, admin, bank_bot, rpg_bot, DEBUG_MODE
except Exception as e:
    print("[CORE] - не получилось импортировать настройки. Файл config.py существует?")
    exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_errors.log'),
        logging.StreamHandler()  # Также выводим в консоль
    ]
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_birthdays, 'cron', hour=1, minute=0, misfire_grace_time=7200)
scheduler.add_job(send_personal_birthday_notifications, 'cron', hour=1, minute=1, misfire_grace_time=7200)
scheduler.add_job(send_weather, 'cron', hour=12, minute=0, misfire_grace_time=7200)
scheduler.add_job(backupBD, 'cron', hour=6, minute=0, misfire_grace_time=7200)
scheduler.start() 

def run_bot(bot_instance, bot_name):
    """Запускает бота в отдельном потоке"""
    logger.info(f"🚀 Запуск {bot_name}...")
    logger.info(f"ID бота {bot_name}: {bot_instance.get_me().id}")
    
    try:
        # ВАЖНО: используем infinity_polling для корректной работы callback-запросов
        bot_instance.infinity_polling(
            timeout=60,
            long_polling_timeout=30,
            logger_level=logging.INFO,
            allowed_updates=['message', 'callback_query', 'edited_message']
        )
    except Exception as e:
        logger.error(f"{bot_name} упал: {e}", exc_info=True)
        time.sleep(10)
        run_bot(bot_instance, bot_name)  # рекурсивный перезапуск

if __name__ == "__main__":
    # Очищаем лог-файл
    with open('bot_errors.log', 'w') as f:
        f.write("=== Новая сессия ===\n")
    
    logger.info("⚠️ ЗАПУСК БОТА В DEBUG MODE!!!!") if DEBUG_MODE else logger.info("🎮 Запускаю всех ботов...") 
    
    # Запускаем каждого бота в отдельном потоке
    threads = []
    
    # Предложка
    t1 = Thread(target=run_bot, args=(predlojka_bot, "Предложка"), daemon=True)
    t1.start()
    threads.append(t1)
    
    if DEBUG_MODE:
        pass

    else:
        # Банк
        t2 = Thread(target=run_bot, args=(bank_bot, "Банк"), daemon=True)
        t2.start()
        threads.append(t2)
        
        # RPG
        t3 = Thread(target=run_bot, args=(rpg_bot, "RPG"), daemon=True)
        t3.start()
        threads.append(t3)
    
    logger.info("✅ Все боты запущены. Ожидание сообщений...")
    
    # Основной поток просто ждёт
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Остановка всех ботов...")
        # scheduler.shutdown()  # если нужно остановить планировщик