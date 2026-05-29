import logging

logger = logging.getLogger(__name__)

class StokerLogger:

    @staticmethod
    def say(message, level="info"):
        """Кочегар общается через логи"""
        if level == "info":
            logger.info(f"📢 {message}")
        elif level == "warn":
            logger.warning(f"⚠️ {message}")
        elif level == "error":
            logger.error(f"💀 {message}")
        elif level == "debug":
            logger.debug(f"🔧 {message}")
    
    @staticmethod
    def start_test_suite():
        StokerLogger.say("🌅 Ну чё, день начинается... Топить будем?")
        StokerLogger.say("🔍 Проверяю систему, как учил старый машинист...", "debug")
        
    @staticmethod
    def test_passed(test_name):
        StokerLogger.say(f"✅ {test_name} - годно! Как в старые добрые...")
        
    @staticmethod
    def test_failed(test_name, error):
        StokerLogger.say(f"❌ {test_name} - НЕ ГОДНО! {error}", "error")
        StokerLogger.say("🔥 Чую, что-то с котлом не то...", "warn")
        
    @staticmethod
    def all_tests_passed():
        StokerLogger.say("🎉 УРА! Все тесты прошли! Можно топку разжигать!")
        StokerLogger.say("💨 Пар пошёл, бот загружается...")
        
    @staticmethod
    def starting_bot(bot_name):
        StokerLogger.say(f"🚂 Запускаю {bot_name}... Держи дверь, ща пару поддадим!")
        
    @staticmethod
    def bot_started(bot_name, bot_id):
        StokerLogger.say(f"✨ {bot_name} (ID: {bot_id}) - работает! Как по маслу!")
        
    @staticmethod
    def bot_crashed(bot_name, error):
        StokerLogger.say(f"💥 {bot_name} рухнул! {error}", "error")
        StokerLogger.say("🔧 Стучу по котлу молотком, перезапускаю...", "warn")
        
    @staticmethod
    def system_ready():
        StokerLogger.say("🎪 ВСЁ! Бот в строю! Могу пойти чайку попить...")
        StokerLogger.say("☕ Кочегар уходит в тень, но следит... Всегда следит.")
        
    @staticmethod
    def debug_mode():
        StokerLogger.say("🔧 РЕЖИМ ОТЛАДКИ! Я буду всё комментировать, даже как угли пересыпаю...", "debug")
        StokerLogger.say("🎭 Ну чё, тестим? Я как в театре...", "debug")