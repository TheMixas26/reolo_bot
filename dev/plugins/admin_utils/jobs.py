from datetime import datetime
from pathlib import Path
from aiogram.types import FSInputFile
from core.core_plugin.stats import EVENTS_LOG_PATH, write_summary_report
from .service import crisis_log, crisis_tg

async def backupDB(context):
    """Создаёт резервную копию базы данных и аналитики и отправляет её в чат бэкапов."""
    async def send_backup_file(path: str | Path, visible_name: str, caption: str) -> None:
        await context.predlojka_bot.send_document(
            context.config.backup_chat,
            FSInputFile(path, filename=visible_name),
            caption=caption,
            disable_notification=True
        )

    try:
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        summary_path = write_summary_report()

        await send_backup_file(
            "dev/database/bot.sqlite3",
            f"db_backup_{date_str}.sqlite3",
            f"📦 Ежедневная порция данных за {date_str}",
        )

        if EVENTS_LOG_PATH.exists():
            await send_backup_file(
                EVENTS_LOG_PATH,
                f"bot_events_{date_str}.jsonl",
                f"📊 Сырой лог статистики за {date_str}",
            )

        if summary_path.exists():
            await send_backup_file(
                summary_path,
                f"bot_stats_summary_{date_str}.txt",
                f"📈 Сводка аналитики за {date_str}",
            )
        
    except Exception as e:
        # ВСЁ ПРОПАЛО, ШЕФ!!!
        error_type = type(e).__name__
        panic_level = "🟡" if "FileNotFound" in error_type else "🔴"
        
        panic_message = f"""
            {panic_level} АААААА!!!! {panic_level}

            НЕ ПОЛУЧИЛОСЬ СОЗДАТЬ РЕЗЕРВНУЮ КОПИЮ БАЗЫ!

            ОШИБКА: {error_type}
            ЧТО СЛОМАЛОСЬ: {str(e)[:75]}

            ПОВТОРЯЮ: БАЗА ДАННЫХ НЕ СОХРАНЕНА!
            ЕСЛИ СЕРВЕР УМРЁТ — ВСЕ ДНИ РОЖДЕНИЯ СГОРЯТ!

            СРОЧНО НА СЕРВЕР!!! ПРЯМО СЕЙЧАС!!! НЕМЕДЛЕННО!!!
        """

        try:
            await crisis_tg(context, f"{panic_message}")
        except:
            crisis_log(context, "🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ КРИЧАТЬ О ПОМОЩИ")
