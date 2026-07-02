from __future__ import annotations

from core.core_plugin.stats import log_event
from .service import get_fallback_message

def _display_name(user) -> str:
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    if getattr(user, "username", None):
        return f"@{user.username}"
    return f"id{user.id}"


def process_ai_message(context, message, content) -> None:
    name = _display_name(message.from_user)
    prompt_text = content.clean_text or message.text
    tg = context.tg_adapter
    response_message = None if content.ignore_reaction else tg.reply_to(message, "Думаю... (*￣3￣)╭")

    log_event("ai_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)

    try:
        full_text = context.ai_service.ask_ai(prompt_text, name)
        if response_message is not None:
            tg.edit_message_text(full_text, chat_id=message.chat.id, message_id=response_message.message_id)
        elif not content.ignore_reaction:
            tg.send_message(message.chat.id, full_text)
        log_event("ai_completed", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)
    except Exception as error:
        context.logger.error(f"Ошибка в AI-запросе: {error}")
        log_event(
            "ai_failed",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"error": str(error)[:300]},
        )
        error_text = get_fallback_message()
        try:
            if response_message is not None:
                tg.edit_message_text(error_text, chat_id=message.chat.id, message_id=response_message.message_id)
            elif not content.ignore_reaction:
                tg.send_message(message.chat.id, error_text)
        except Exception:
            if not content.ignore_reaction:
                tg.send_message(message.chat.id, "Извините, ошибка обработки...")


def register_handlers(context) -> None:
    logger = context.logger_factory("ai", persona="Варя")
    logger.say("AI-плагин подключён. #ai обрабатывается через предложку.")
