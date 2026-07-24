from __future__ import annotations

import asyncio
from dataclasses import dataclass
from logging import Logger
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.background import BackgroundScheduler

from core.core_plugin.stats import log_event

from aiogram.client.default import DefaultBotProperties


@dataclass(slots=True)
class BotRuntime:
    name: str
    token: str
    display_name: str
    bot: Bot
    dispatcher: Dispatcher


def create_bot(token: str, *, parse_mode: str = "HTML") -> Bot:
    if DefaultBotProperties is not None:
        return Bot(token=token, default=DefaultBotProperties(parse_mode=parse_mode))
    return Bot(token=token, parse_mode=parse_mode)


class AppContext:
    def __init__(
        self,
        scheduler: BackgroundScheduler,
        logger: Logger,
        config: Any,
        admin_id: int,
        chat_mishas_den: int,
        channel: int,
        debug_status: bool,
        hybernation_status: bool,
        ai_service: Any | None = None,
        telegram_admin_target: Any | None = None,
    ):
        self.scheduler = scheduler
        self.logger = logger
        self.config = config
        self.admin_id = admin_id
        self.admin = admin_id
        self.chat_mishas_den = chat_mishas_den
        self.channel = channel
        self.debug_status = debug_status
        self.hybernation_status = hybernation_status
        self.ai_service = ai_service
        self.telegram_admin_target = telegram_admin_target
        self.telegram_runtimes: dict[str, BotRuntime] = {}
        self.logger_factory = self._make_logger_factory()

        self.predlojka_bot: Bot | None = None
        self.bank_bot: Bot | None = None
        self.rpg_bot: Bot | None = None
        self.dp: Dispatcher | None = None

    def token_for(self, bot_name: str) -> str:
        token_attr = f"{bot_name.upper()}_TOKEN"
        token = getattr(self.config, token_attr, None)
        if not token:
            raise RuntimeError(f"Не задан {token_attr} в config.py")
        return token

    def ensure_bot(
        self,
        bot_name: str,
        token: str | None = None,
        *,
        display_name: str | None = None,
        parse_mode: str = "HTML",
    ) -> Bot:
        runtime = self.telegram_runtimes.get(bot_name)
        if runtime is None:
            bot = create_bot(token or self.token_for(bot_name), parse_mode=parse_mode)
            dispatcher = Dispatcher(storage=MemoryStorage())
            runtime = BotRuntime(
                name=bot_name,
                token=token or self.token_for(bot_name),
                display_name=display_name or bot_name,
                bot=bot,
                dispatcher=dispatcher,
            )
            self.telegram_runtimes[bot_name] = runtime
            setattr(self, f"{bot_name}_bot", bot)
            if bot_name == "predlojka":
                self.dp = dispatcher
        return runtime.bot

    def include_router(self, bot_name: str, router) -> None:
        runtime = self.telegram_runtimes.get(bot_name)
        if runtime is None:
            self.ensure_bot(bot_name)
            runtime = self.telegram_runtimes[bot_name]
        runtime.dispatcher.include_router(router)

    def aiogram_bot(self, bot_name: str) -> Bot:
        return self.telegram_runtimes[bot_name].bot

    def dispatcher(self, bot_name: str) -> Dispatcher:
        return self.telegram_runtimes[bot_name].dispatcher

    async def start_telegram_bots(self) -> None:
        if not self.telegram_runtimes:
            self.logger.warning("Нет зарегистрированных Telegram-ботов для запуска.")
            return

        async def _start(runtime: BotRuntime):
            restart_delay = 10.0
            persona = self.logger_factory(runtime.name, persona=runtime.display_name)
            while True:
                try:
                    bot_info = await runtime.bot.get_me()
                    persona.say(f"{runtime.display_name} запущен. Telegram ID: {bot_info.id}")
                    log_event(
                        "bot_started",
                        bot=runtime.name,
                        metadata={"telegram_bot_id": bot_info.id, "display_name": runtime.display_name},
                    )
                    await runtime.dispatcher.start_polling(
                        runtime.bot,
                        allowed_updates=["message", "callback_query", "edited_message"],
                    )
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    persona.say(f"{runtime.display_name} упал: {error}", "error")
                    log_event(
                        "bot_crashed",
                        bot=runtime.name,
                        metadata={"display_name": runtime.display_name, "error": str(error)[:300]},
                    )
                    await asyncio.sleep(restart_delay)
                    restart_delay = min(restart_delay * 1.5, 60.0)

        await asyncio.gather(*(_start(runtime) for runtime in self.telegram_runtimes.values()))

    async def close_telegram_bots(self) -> None:
        for runtime in self.telegram_runtimes.values():
            result = runtime.bot.session.close()
            if hasattr(result, "__await__"):
                await result

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
