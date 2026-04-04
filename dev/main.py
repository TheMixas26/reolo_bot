"""Точка входа в бота, запускайте именно этот файл."""

from analytics.stats import log_event
from handlers import user_handlers, admin_handlers, misc_handlers, achievements_handlers, predlojka_handlers, bank_handlers, vk_handlers
from handlers.card_handlers import callbacks as card_callbacks
from handlers.card_handlers import commands as card_commands
from posting.runtime import vk_adapter
from utils.schedulers import scheduler

import logging
from threading import Thread
import time
import utils.schedulers # Импортируем планировщик, чтобы он запустился
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

def run_bot(bot_instance, bot_name, analytics_bot_name):
    """Запускает бота в отдельном потоке"""
    logger.info(f"🚀 Запуск {bot_name}...")
    bot_info = bot_instance.get_me()
    logger.info(f"ID бота {bot_name}: {bot_info.id}")
    log_event("bot_started", bot=analytics_bot_name, metadata={"telegram_bot_id": bot_info.id, "display_name": bot_name})
    
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
        log_event("bot_crashed", bot=analytics_bot_name, metadata={"display_name": bot_name, "error": str(e)[:300]})
        time.sleep(10)
        log_event("bot_restart_scheduled", bot=analytics_bot_name, metadata={"display_name": bot_name})
        run_bot(bot_instance, bot_name, analytics_bot_name)  # рекурсивный перезапуск

if __name__ == "__main__":
    # Очищаем лог-файл
    with open('bot_errors.log', 'w') as f:
        f.write("=== Новая сессия ===\n")

    if scheduler.get_job("publish_scheduled_posts") is None:
        scheduler.add_job(
            predlojka_handlers.publish_due_scheduled_posts,
            "interval",
            minutes=1,
            id="publish_scheduled_posts",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )
    
    logger.info("⚠️ ЗАПУСК БОТА В DEBUG MODE!!!!") if DEBUG_MODE else logger.info("🎮 Запускаю всех ботов...") 
    log_event("system_bootstrap", bot="system", metadata={"debug_mode": DEBUG_MODE})
    
    # Запускаем каждого бота в отдельном потоке
    threads = []
    
    # Предложка
    t1 = Thread(target=run_bot, args=(predlojka_bot, "Предложка", "predlojka"), daemon=True)
    t1.start()
    threads.append(t1)
    
    
    # RPG
    t2 = Thread(target=run_bot, args=(rpg_bot, "RPG", "rpg"), daemon=True)
    t2.start()
    threads.append(t2)

    if vk_adapter is not None:
        t_vk = Thread(target=vk_handlers.run_vk_listener, daemon=True)
        t_vk.start()
        threads.append(t_vk)

    if DEBUG_MODE:
        pass
        
    else:
        # Банк
        t3 = Thread(target=run_bot, args=(bank_bot, "Банк", "bank"), daemon=True)
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
