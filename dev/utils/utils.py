from random import choice, random
from pathlib import Path
from datetime import datetime
from varibles.dialogue_loader import TEXT

from telebot import types

from analytics.stats import EVENTS_LOG_PATH, write_summary_report
from config import predlojka_bot, admin, backup_chat
from settings import render_text_template

COMMANDS_FILE_PATH = Path("dev/varibles/command_list.txt")

def thx_for_message(user_name: str, mes_type: str) -> str:
    FUN = random.random()

    if mes_type == '!':
        if FUN < 0.9:
            return TEXT("thx", "variants_v", name=user_name)
        elif FUN >= 0.98:
            return TEXT("thx", "podval_variants_v", name=user_name)
        else:
            return TEXT("thx", "secret_variants_v", name=user_name)

    elif mes_type == '?':
        return TEXT("thx", "variants_q", name=user_name)

    elif mes_type == 'event':
        return TEXT("thx", "events_variants")

    elif mes_type == 'report':
        return TEXT("thx", "report_variants")

    elif mes_type == 'message':
        return TEXT("thx", "message_variants")

    else:
        return TEXT("thx", "variants_v", name=user_name)


def _normalize_section_name(raw_name: str) -> str:
    return raw_name.strip().strip("[]").strip().lower()


def _load_command_registry() -> dict[str, list[types.BotCommand]]:
    registry: dict[str, list[types.BotCommand]] = {}
    current_section = "predlojka_user"

    try:
        with COMMANDS_FILE_PATH.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.startswith("[") and line.endswith("]"):
                    current_section = _normalize_section_name(line)
                    registry.setdefault(current_section, [])
                    continue

                parts = line.split(" - ", 1)
                if len(parts) != 2:
                    print(f"Неправильный формат строки: {line}")
                    continue

                command, description = parts
                registry.setdefault(current_section, []).append(
                    types.BotCommand(command.strip(), render_text_template(description.strip()))
                )

    except FileNotFoundError:
        predlojka_bot.send_message(
            admin,
            "Товарищ администратор, тут нюансик такой... Я не смогла найти файл с командами для бота... Проверьте это как можно скорее! (ಥ﹏ಥ)",
        )
        registry["predlojka_user"] = [
            types.BotCommand("start", "Запустить бота"),
            types.BotCommand("help", "Помощь"),
        ]

    return registry


def get_commands_for_set(bot_name: str = "predlojka", include_admin: bool = False) -> list[types.BotCommand]:
    registry = _load_command_registry()
    user_section = registry.get(f"{bot_name}_user", [])
    if not include_admin:
        return user_section
    admin_section = registry.get(f"{bot_name}_admin", [])
    return user_section + admin_section


def crisis_log(message: str):
    for i in range(100):
        print(message)


def crisis_tg(message: str):
    """Отправляет администратору сообщение о критической ошибке"""
    try:
        for i in range(10):
            predlojka_bot.send_message(
                admin,
                message,
                parse_mode='HTML',
                disable_notification=False
            )
    except:
        crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ СООБЩИТЬ О КРИЗИСЕ")


def backupDB():
    """Создаёт резервную копию базы данных и аналитики и отправляет её в чат бэкапов."""
    def send_backup_file(path: str | Path, visible_name: str, caption: str) -> None:
        with open(path, mode='rb') as file:
            predlojka_bot.send_document(
                backup_chat,
                file,
                visible_file_name=visible_name,
                caption=caption,
                disable_notification=True
            )

    try:
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        summary_path = write_summary_report()

        send_backup_file(
            "dev/database/bot.sqlite3",
            f"db_backup_{date_str}.sqlite3",
            f"📦 Ежедневная порция данных за {date_str}",
        )

        if EVENTS_LOG_PATH.exists():
            send_backup_file(
                EVENTS_LOG_PATH,
                f"bot_events_{date_str}.jsonl",
                f"📊 Сырой лог статистики за {date_str}",
            )

        if summary_path.exists():
            send_backup_file(
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
            crisis_tg(f"{panic_message}")
        except:
            crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ КРИЧАТЬ О ПОМОЩИ")


def bot_reboot():
    """Перезапускает бота (на всякий случай, если он зависнет)"""
    try:
        predlojka_bot.send_message(
            backup_chat,
            "🤖 Бот перезагружается... Если вы видите это сообщение, значит перезагрузка прошла успешно!"
        )
    except:
        
        crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ СООБЩИТЬ О ПЕРЕЗАГРУЗКЕ")
    
    # Рекурсивный вызов функции для перезапуска бота
    import os
    import sys
    os.execv(sys.executable, ['python'] + sys.argv)


if __name__ == "__main__":
    print(get_commands_for_set("predlojka", include_admin=True))
