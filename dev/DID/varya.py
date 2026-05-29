import logging

logger = logging.getLogger(__name__)

class VaryaStokerLogger:
    
    @staticmethod
    def say(message, level="info"):
        """Варя общается через логи"""
        if level == "info":
            logger.info(f"📢 {message}")
        elif level == "warn":
            logger.warning(f"⚠️ {message}")
        elif level == "error":
            logger.error(f"💀 {message}")
        elif level == "debug":
            logger.debug(f"🔧 {message}")
