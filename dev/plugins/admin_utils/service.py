from settings import render_text_template
from core.core_plugin.stats import log_command_usage, log_event
from varibles.dialogue_loader import TEXT
from telebot import types
from pathlib import Path

COMMANDS_FILE_PATH = Path("dev/varibles/command_list.txt")


def set_commands(context, message=None):
        if message and message.from_user.id != context.admin_id:
            return
        
        scope = types.BotCommandScopeChat(context.admin_id)

        context.predlojka_bot.set_my_commands(get_commands_for_set(context, "predlojka"))
        context.predlojka_bot.set_my_commands(
            get_commands_for_set(context, "predlojka", include_admin=True),
            scope=scope
        )
        context.bank_bot.set_my_commands(get_commands_for_set(context, "bank"))
        context.rpg_bot.set_my_commands(get_commands_for_set(context, "rpg"))
        context.rpg_bot.set_my_commands(
            get_commands_for_set(context, "rpg", include_admin=True),
            scope=scope,
        )

        if message:
            log_command_usage("predlojka", "setcmd", message)
        log_event("commands_synced", bot="system", metadata={"triggered_by": message.from_user.id if message else "scheduler"})

        if message:
            context.predlojka_bot.reply_to(message, TEXT('setcmd_successfully'))



def crisis_log(context, message: str):
    for i in range(100):
        context.logger.error(message)


def crisis_tg(context, message: str):
    """Отправляет администратору сообщение о критической ошибке"""
    try:
        for i in range(10):
            context.predlojka_bot.send_message(
                context.admin,
                message,
                parse_mode='HTML',
                disable_notification=False
            )
    except:
        crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ СООБЩИТЬ О КРИЗИСЕ")


def get_commands_for_set(context, bot_name: str = "predlojka", include_admin: bool = False) -> list[types.BotCommand]:
    registry = _load_command_registry(context)
    user_section = registry.get(f"{bot_name}_user", [])
    if not include_admin:
        return user_section
    admin_section = registry.get(f"{bot_name}_admin", [])
    return user_section + admin_section

def _normalize_section_name(raw_name: str) -> str:
    return raw_name.strip().strip("[]").strip().lower()


def _load_command_registry(context) -> dict[str, list[types.BotCommand]]:
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
                    context.logger.warning(f"Неправильный формат строки: {line}")
                    continue

                command, description = parts
                registry.setdefault(current_section, []).append(
                    types.BotCommand(command.strip(), render_text_template(description.strip()))
                )

    except FileNotFoundError:
        context.predlojka_bot.send_message(
            context.admin,
            "Товарищ администратор, тут нюансик такой... Я не смогла найти файл с командами для бота... Проверьте это как можно скорее! (ಥ﹏ಥ)",
        )
        registry["predlojka_user"] = [
            types.BotCommand("start", "Запустить бота"),
            types.BotCommand("help", "Помощь"),
        ]

    return registry
