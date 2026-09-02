import asyncio
from datetime import datetime
from pathlib import Path

from aiogram.types import FSInputFile

from core.core_plugin.stats import EVENTS_LOG_PATH, write_summary_report
from .service import crisis_log, crisis_tg


async def backupDB(context):
    """Создаёт резервную копию PostgreSQL и аналитики и отправляет её в чат бэкапов."""

    async def send_backup_file(
        path: str | Path,
        visible_name: str,
        caption: str,
    ) -> None:
        await context.predlojka_bot.send_document(
            context.config.backup_chat,
            FSInputFile(path, filename=visible_name),
            caption=caption,
            disable_notification=True,
        )

    backup_dir = Path("dev/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        summary_path = write_summary_report()

        db_backup_path = backup_dir / f"db_backup_{date_str}.dump"

        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-Fc",
            "-f",
            str(db_backup_path),
            context.config.DATABASE_URL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                f"pg_dump завершился с кодом {process.returncode}: "
                f"{stderr.decode(errors='replace')[:500]}"
            )

        if not db_backup_path.exists():
            raise FileNotFoundError(
                f"pg_dump завершился успешно, но файл {db_backup_path} не найден"
            )

        # TODO: texts.json
        await send_backup_file(
            db_backup_path,
            db_backup_path.name,
            f"📦 Резервная копия PostgreSQL за {date_str}",
        )

        if EVENTS_LOG_PATH.exists():
            # TODO: texts.json
            await send_backup_file(
                EVENTS_LOG_PATH,
                f"bot_events_{date_str}.jsonl",
                f"📊 Сырой лог статистики за {date_str}",
            )

        if summary_path.exists():
            await send_backup_file(
                # TODO: texts.json
                summary_path,
                f"bot_stats_summary_{date_str}.txt",
                f"📈 Сводка аналитики за {date_str}",
            )

        db_backup_path.unlink(missing_ok=True)

    except Exception as e:
        # ВСЁ ПРОПАЛО, ШЕФ!!!
        error_type = type(e).__name__
        panic_level = "🟡" if "FileNotFound" in error_type else "🔴"

        # TODO: texts.json
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
            await crisis_tg(context, panic_message)
        except Exception:
            crisis_log(
                context,
                "🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ КРИЧАТЬ О ПОМОЩИ",
            )
