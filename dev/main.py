"""Точка входа в бота, запускайте именно этот файл."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import argparse

import config as cfg
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.context import AppContext
from core.core_plugin import CorePlugin
from core.core_plugin.stats import log_event

from plugins import *

from plugins.ai import AIService

from varibles.dialogue_loader import load_texts
from varibles import TEXT

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
    SponsorshipPlugin,
    MafiaPlugin,
]

load_texts(enabled_plugins)

CorePlugin.setup(context)
for plugin in enabled_plugins:
    plugin.setup(context)


async def run_pre_launch_tests():
    kochegar.say("Проверяю систему перед запуском.")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pytest",
        "-q",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        stdout, _ = await proc.communicate()
    except asyncio.CancelledError:
        try:
            proc.terminate()
        except Exception:
            pass
        raise

    exit_code = proc.returncode
    if stdout:
        try:
            kochegar.say(stdout.decode(errors="ignore"))
        except Exception:
            pass

    if exit_code == 0:
        kochegar.say("Тесты прошли, запускаю polling.")
        return True

    kochegar.say("Тесты не прошли, боты не будут запущены.", "error")
    return False


async def run(skip_tests: bool = False, notify_admin: bool = False) -> None:
    with open("bot_errors.log", "w", encoding="utf-8") as file:
        file.write("=== Новая сессия ===\n")
        file.write("КОЧЕГАР ЗАСТУПИЛ НА СМЕНУ\n\n")

    kochegar.say("Система стартует.")
    log_event("system_bootstrap", bot="system", metadata={"debug_mode": DEBUG_MODE})

    if skip_tests:
        kochegar.say("Сверху приказ деплоить без тестов.")
        kochegar.say("Стартуем без проверки безопасности!")
        logger.info("⚠️ Запуск с пропуском тестов")
    else:
        if not await run_pre_launch_tests():
            raise SystemExit(1)

    if args.all_texts:
        kochegar.say("Хочу увидеть пьесу целиком!")
        logger.info("📋 Создание all_texts.json...")
        from varibles.dialogue_loader import see_drama_script
        see_drama_script()

    scheduler.start()
    varya.say("Я на месте. (•̀ᴗ•́)و")

    try:
        await context.start_telegram_bots()
    finally:
        scheduler.shutdown(wait=False)
        if notify_admin:
            await context.predlojka_bot.send_message(context.admin, TEXT("successfully_started"))
        
        await context.close_telegram_bots()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Запуск бота")
    parser.add_argument("--skip-tests", action="store_true", help="Пропустить предварительные тесты")
    parser.add_argument("--all-texts", action="store_true", help="Создать единный файл со всеми текстами")
    parser.add_argument("--notify-admin", action="store_true", help="Оповестить админа об успешном запуске")
    args = parser.parse_args()
    # TODO: Добавить больше полезных и интересных аргументов, мало ли, пригодится



    import signal
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_event = asyncio.Event()

    def _on_signal() -> None:
        kochegar.say("Остановка по сигналу.")
        logger.info("Остановка всех ботов.")

        try:
            stop_event.set()
        except Exception:
            pass
        # ctrl+C не работает вашу мать, я когда-нибудь уже починю этот шизофренический бред???
        # Похер, фиганём ФУНКЦИЮ ДЛЯ ВЫКЛЮЧЕНИЯ БЛЯТЬ
        async def _shutdown():
            """
            P.S. Эта херня работает!!!! Вызывая ошибку на очень много строк.... Но это успешно завершает процесс!!!!
            Когда-нибудь я это исправлю, TODO: почини это
            """
            try:
                # -задачи
                try:
                    scheduler.shutdown(wait=False)
                except Exception:
                    pass

                # умоляю на коленях ботов выключиться
                try:
                    await context.close_telegram_bots()
                except Exception:
                    pass

                # прочая ересь, мало ли, что там ещё мешает мне
                current = asyncio.current_task()
                tasks = [t for t in asyncio.all_tasks() if t is not current]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                try:
                    loop.stop()
                except Exception:
                    pass

        try:
            loop.call_soon_threadsafe(lambda: asyncio.create_task(_shutdown()))
        except Exception:
            pass

    for _sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(_sig, _on_signal)
        except NotImplementedError:
            pass

    async def _run_and_wait():
        task = asyncio.create_task(run(skip_tests=args.skip_tests, notify_admin=args.notify_admin))
        await stop_event.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        loop.run_until_complete(_run_and_wait())
    finally:
        loop.close()