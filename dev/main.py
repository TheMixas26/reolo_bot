"""Точка входа в бота, запускайте именно этот файл."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys

import config as cfg
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.context import AppContext
from core.core_plugin import CorePlugin
from core.core_plugin.stats import log_event
from plugins.achievements import AchievementsPlugin
from plugins.admin_utils import AdminUtilsPlugin
from plugins.ai import AIPlugin, AIService
from plugins.bank import BankPlugin
from plugins.birthdays import BirthdaysPlugin
from plugins.calendar import CalendarPlugin
from plugins.cardgame import CardGamePlugin
from plugins.predlojka import PredlojkaPlugin
from plugins.weather import WeatherPlugin
from varibles.dialogue_loader import load_texts

# from plugins.vk import VKPlugin


DEBUG_MODE = getattr(cfg, "DEBUG_MODE", False)
HIBERNATION = getattr(cfg, "HIBERNATION", False)


logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot_errors.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

ai_service = AIService(
    catalog_id=getattr(cfg, "CATALOG_ID", ""),
    secret_key=getattr(cfg, "SECRET_KEY", ""),
    logger=logger.getChild("ai"),
)

scheduler = AsyncIOScheduler()

context = AppContext(
    scheduler=scheduler,
    logger=logger,
    config=cfg,
    admin_id=cfg.admin,
    chat_mishas_den=cfg.chat_mishas_den,
    channel=cfg.channel,
    debug_status=DEBUG_MODE,
    hybernation_status=HIBERNATION,
    ai_service=ai_service,
    telegram_admin_target=cfg.admin,
)

kochegar = context.logger_factory("core", persona="Кочегар")
varya = context.logger_factory("predlojka", persona="Варя")


enabled_plugins = [
    # PredlojkaPlugin,
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
    kochegar.say("Проверяю систему перед запуском.")

    exit_code = subprocess.call([sys.executable, "-m", "pytest", "-v"])

    if exit_code == 0:
        kochegar.say("Тесты прошли, запускаю polling.")
        return True

    kochegar.say("Тесты не прошли, боты не будут запущены.", "error")
    return False


async def run() -> None:
    with open("bot_errors.log", "w", encoding="utf-8") as file:
        file.write("=== Новая сессия ===\n")
        file.write("КОЧЕГАР ЗАСТУПИЛ НА СМЕНУ\n\n")

    kochegar.say("Система стартует.")
    log_event("system_bootstrap", bot="system", metadata={"debug_mode": DEBUG_MODE})

    if not run_pre_launch_tests():
        raise SystemExit(1)

    scheduler.start()
    varya.say("Я на месте.")

    try:
        await context.start_telegram_bots()
    finally:
        scheduler.shutdown(wait=False)
        await context.close_telegram_bots()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        kochegar.say("Остановка по Ctrl+C.")
        logger.info("Остановка всех ботов.")
