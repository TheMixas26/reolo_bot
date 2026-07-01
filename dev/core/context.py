from telebot import TeleBot
from apscheduler.schedulers.background import BackgroundScheduler
from logging import Logger
from typing import Any

class AppContext:
    def __init__(
        self,
        predlojka_bot: TeleBot,
        bank_bot: TeleBot,
        rpg_bot: TeleBot,
        scheduler: BackgroundScheduler,
        logger: Logger,
        config: Any,
        tg_adapter,
        bank_adapter,
        admin_id: int,
        chat_mishas_den: int,
        channel: int,
        ai_service: Any | None = None,
        post_publisher: Any | None = None,
        telegram_admin_target: Any | None = None,
    ):
        self.predlojka_bot = predlojka_bot
        self.bank_bot = bank_bot
        self.rpg_bot = rpg_bot
        self.scheduler = scheduler
        self.logger = logger
        self.config = config
        self.tg_adapter = tg_adapter
        self.bank_adapter = bank_adapter
        self.admin_id = admin_id
        self.chat_mishas_den = chat_mishas_den
        self.channel = channel
        self.ai_service = ai_service
        self.post_publisher = post_publisher
        self.telegram_admin_target = telegram_admin_target
        self.logger_factory = self._make_logger_factory()


    def _make_logger_factory(self):
        base_logger = self.logger

        def factory(name: str, persona: str | None = None):
            child = base_logger.getChild(name)

            def log(message, level="info"):
                prefix = f"[{persona or name}]"

                if level == "info":
                    child.info(f"{prefix} {message}")
                elif level in ["warn", "warning"]:
                    child.warning(f"{prefix} {message}")
                elif level == "error":
                    child.error(f"{prefix} {message}")
                elif level == "debug":
                    child.debug(f"{prefix} {message}")

            return type("PluginLogger", (), {"say": log})

        return factory
