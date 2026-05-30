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
        admin_id: int,
    ):
        self.predlojka_bot = predlojka_bot
        self.bank_bot = bank_bot
        self.rpg_bot = rpg_bot
        self.scheduler = scheduler
        self.logger = logger
        self.config = config
        self.tg_adapter = tg_adapter
        self.admin_id = admin_id