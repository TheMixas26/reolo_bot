"""Точка входа в бота, запускайте именно этот файл."""

from core.core_plugin.stats import log_event
import config as cfg
from varibles.dialogue_loader import load_texts
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess

import logging
from threading import Thread
import time
import sys

from core.context import AppContext
from core.core_plugin import CorePlugin
from plugins.predlojka import PredlojkaPlugin
# from plugins.vk import VKPlugin
from plugins.birthdays import BirthdaysPlugin
from plugins.weather import WeatherPlugin
from plugins.ai import AIPlugin, AIService
from plugins.admin_utils import AdminUtilsPlugin
from plugins.bank import BankPlugin
from plugins.achievements import AchievementsPlugin
from plugins.calendar import CalendarPlugin
from plugins.cardgame import CardGamePlugin

try:
    from config import predlojka_bot, admin, channel, chat_mishas_den, bank_bot, rpg_bot, DEBUG_MODE, HIBERNATION
except Exception as e:
    print(f"[КОЧЕГАР] - Ё-моё, настройки не грузятся! {e}")
    exit(1)


logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_errors.log', encoding='utf-8'),
        logging.StreamHandler()
    ])



logger = logging.getLogger(__name__)

ai_service = AIService(
    catalog_id=cfg.CATALOG_ID,
    secret_key=cfg.SECRET_KEY,
    logger=logger.getChild("ai"),
)

scheduler = BackgroundScheduler()


context = AppContext(
    predlojka_bot=predlojka_bot,
    bank_bot=bank_bot,
    rpg_bot=rpg_bot,
    scheduler=scheduler,
    logger=logger,
    config=cfg,
    admin_id=admin,
    chat_mishas_den=chat_mishas_den,
    channel=channel,
    debug_status=DEBUG_MODE,
    hybernation_status=HIBERNATION,
    ai_service=ai_service,
    telegram_admin_target=admin,
)


kochegar = context.logger_factory("core", persona="Кочегар")
varya = context.logger_factory("predlojka", persona="Варя")


enabled_plugins = [
    PredlojkaPlugin,
    BirthdaysPlugin,
    WeatherPlugin,
    AIPlugin,
    # VKPlugin,
    AdminUtilsPlugin,
    BankPlugin,
    AchievementsPlugin,
    CalendarPlugin,
    CardGamePlugin,
]

load_texts(enabled_plugins)

CorePlugin.setup(context)
for plugin in enabled_plugins:
    plugin.setup(context)



def run_pre_launch_tests():    
    kochegar.say("🌅 Ну чё, день начинается... Топить будем?")
    kochegar.say("🔍 Проверяю систему, как учил старый машинист...", "debug")
    kochegar.say("🔧 Эй, pytest, проверь-ка систему!")
    
    # Просто запускаем pytest и смотрим на код возврата
    exit_code = subprocess.call([sys.executable, "-m", "pytest", "tests/", "-v"])
    
    if exit_code == 0:
        kochegar.say("✅ Всё пучком! Тесты прошли!")
        kochegar.say("🎉 УРА! Все тесты прошли! Можно топку разжигать!")
        kochegar.say("💨 Пар пошёл, бот загружается...")
        return True
    else:
        kochegar.say("💀 ТЕСТЫ НЕ ПРОШЛИ! Смотри выше, где pytest ругается", "error")
        kochegar.say("🧹 Чини, а я пока золу выгребу...", "warn")
        return False

def run_bot(bot_instance, bot_name, analytics_bot_name):
    """Запускает бота в отдельном потоке (с комментариями Кочегара)"""
    restart_delay = 10

    while True:

        kochegar.say(f"🚂 Запускаю {bot_name}... Держи дверь, ща пару поддадим!")
        try:
            bot_info = bot_instance.get_me()
            kochegar.say(f"✨ {bot_name} (ID: {bot_info.id}) - работает! Как по маслу!")
            log_event("bot_started", bot=analytics_bot_name, metadata={"telegram_bot_id": bot_info.id, "display_name": bot_name})
            
            # Запускаем polling
            bot_instance.infinity_polling(
                timeout=60,
                long_polling_timeout=30,
                logger_level=logging.INFO,
                allowed_updates=['message', 'callback_query', 'edited_message']
            )
        except Exception as e:
            kochegar.say(f"💥 {bot_name} рухнул! {e}", "error")
            kochegar.say("🔧 Стучу по котлу молотком, перезапускаю...", "warn")
            log_event("bot_crashed", bot=analytics_bot_name, metadata={"display_name": bot_name, "error": str(e)[:300]})
            kochegar.say("🔄 Кочегар стучит по трубам, пробуем снова...")
            time.sleep(restart_delay)
            restart_delay = min(restart_delay * 1.5, 60)


if __name__ == "__main__":
    # Очищаем лог-файл
    with open('bot_errors.log', 'w', encoding='utf-8') as f:
        f.write("=== Новая сессия ===\n")
        f.write("🔥 КОЧЕГАР ЗАСТУПИЛ НА СМЕНУ 🔥\n\n")
    
    kochegar.say("🏭 Здорово, работяги! Кочегар на месте, топка горит!")

    if DEBUG_MODE:
        kochegar.say("🔧 РЕЖИМ ОТЛАДКИ! Я буду всё комментировать, даже как угли пересыпаю...", "debug")
    else:
        kochegar.say("🎮 ПРОДАКШН РЕЖИМ: Все системы на пределе, жми на газ!")
    
    log_event("system_bootstrap", bot="system", metadata={"debug_mode": DEBUG_MODE})
    
    # ========== КОЧЕГАР ЗАПУСКАЕТ ТЕСТЫ ==========
    kochegar.say("🔧 ТЕПЕРЬ ТЕСТЫ! Кочегар всё проверит...")
    
    if not run_pre_launch_tests():
        kochegar.say("💀 ТЕСТЫ НЕ ПРОШЛИ! Боты не будет запущены!", "error")
        kochegar.say("📝 Смотри лог выше, я там всё написал...")
        sys.exit(1)
    
    # ========== ТЕСТЫ ПРОШЛИ - ЗАПУСКАЕМ БОТОВ ==========
    scheduler.start()

    kochegar.say("🎉 УРА! ТЕСТЫ ПРОШЛИ! ЗАПУСКАЮ ВСЕХ БОТОВ!")
    
    threads = []
    
    # Предложка
    t1 = Thread(target=run_bot, args=(predlojka_bot, "ПРЕДЛОЖКА", "predlojka"), daemon=True)
    t1.start()
    threads.append(t1)
    varya.say("Я на месте!!!")
    
    # RPG
    t2 = Thread(target=run_bot, args=(rpg_bot, "RPG", "rpg"), daemon=True)
    t2.start()
    threads.append(t2)
    kochegar.say("🎲 RPG бот запущен")
    
    
    t3 = Thread(target=run_bot, args=(bank_bot, "БАНК", "bank"), daemon=True)
    t3.start()
    threads.append(t3)
    kochegar.say("💰 Банковский бот запущен")

    kochegar.say("🎪 ВСЁ! Бот в строю! Могу пойти чайку попить...")
    kochegar.say("☕ Кочегар уходит в тень, но следит... Всегда следит.")
    
    # Основной поток просто ждёт
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        kochegar.say("👋 Всё, Кочегар уходит... Золу выгреб, дверь закрыл. Пока, работяги!")
        logger.info("🛑 Остановка всех ботов...")
        # scheduler.shutdown()  # если нужно остановить планировщик
