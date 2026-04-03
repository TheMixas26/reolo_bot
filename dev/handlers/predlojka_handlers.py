from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass

from telebot import types

from ai.ai_module import stream_ai
from analytics.stats import log_event
from config import predlojka_bot, admin, channel, channel_red, chat_mishas_den
from database.sqlite_db import add_to_post_counter, create_user_if_missing, user_exists
from utils.utils import thx_for_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

q = types.ReplyKeyboardRemove()
media_groups_buffer: dict[str, list] = {}
media_groups_timer: dict[str, threading.Timer] = {}
moderation_queue: dict[int, dict] = {}
album_queue: dict[int, dict] = {}
pending_question_answers: dict[int, dict] = {}

MEDIA_GROUP_TIMEOUT = 2.0
CONTROL_TAGS = {"#анон", "#вопрос", "#ai"}
TAG_PATTERN = re.compile(r"(?<!\w)#[\wа-яА-ЯёЁ]+", re.UNICODE)
BLOCKED_SUBMISSION_CHATS = {channel, channel_red, chat_mishas_den}


@dataclass
class SubmissionContent:
    clean_text: str
    public_tags: list[str]
    is_anonymous: bool
    is_question: bool
    wants_ai: bool


def safe_delete_message(chat_id: int, message_id: int, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            predlojka_bot.delete_message(chat_id, message_id)
            return True
        except Exception as error:
            logger.error(f"Ошибка при удалении сообщения {message_id} (попытка {attempt + 1}): {error}")
            time.sleep(0.4)
    return False


def safe_send_media_group(chat_id: int, media: list, max_retries: int = 3) -> list | None:
    for attempt in range(max_retries):
        try:
            return predlojka_bot.send_media_group(chat_id, media)
        except Exception as error:
            logger.error(f"Ошибка при отправке медиагруппы (попытка {attempt + 1}): {error}")
            if attempt < max_retries - 1:
                time.sleep(1)
    return None


def _display_name(user) -> str:
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    if getattr(user, "username", None):
        return f"@{user.username}"
    return f"id{user.id}"


def _can_use_ai(chat_id: int) -> bool:
    return chat_id == chat_mishas_den or chat_id not in BLOCKED_SUBMISSION_CHATS


def _can_submit_post(chat_id: int) -> bool:
    return chat_id not in BLOCKED_SUBMISSION_CHATS


def _parse_submission_text(text: str | None) -> SubmissionContent:
    raw_text = text or ""
    public_tags: list[str] = []
    seen_tags: set[str] = set()
    flags = {"#анон": False, "#вопрос": False, "#ai": False}

    def _replace_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        normalized = tag.lower()
        if normalized in flags:
            flags[normalized] = True
        else:
            public_tag = normalized
            if public_tag not in seen_tags:
                seen_tags.add(public_tag)
                public_tags.append(public_tag)
        return ""

    clean_text = TAG_PATTERN.sub(_replace_tag, raw_text)
    clean_text = re.sub(r"[ \t]+", " ", clean_text)
    clean_text = re.sub(r" *\n *", "\n", clean_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    return SubmissionContent(
        clean_text=clean_text,
        public_tags=public_tags,
        is_anonymous=flags["#анон"],
        is_question=flags["#вопрос"],
        wants_ai=flags["#ai"],
    )


def _compose_publish_text(content: SubmissionContent, user_name: str) -> str:
    parts: list[str] = []
    if content.clean_text:
        parts.append(content.clean_text)
    if content.public_tags:
        parts.append("🏷️ " + " ".join(content.public_tags))
    parts.append("🤫 Аноним" if content.is_anonymous else f"👤 {user_name}")
    return "\n\n".join(parts).strip()


def _escape_markdown_v2(text: str) -> str:
    escaped = text or ""
    for char in ("\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def _format_markdown_quote(text: str) -> str:
    lines = (text or "").splitlines() or [""]
    return "\n".join(f"> {_escape_markdown_v2(line)}" if line else ">" for line in lines)


def _fallback_question_text(payload: dict) -> str:
    content_type = payload["content_type"]
    mapping = {
        "sticker": "Пользователь прислал вопрос в виде стикера. (стоп, что)",
        "photo": "Пользователь прислал вопрос вместе с фотографией.",
        "video": "Пользователь прислал вопрос вместе с видео.",
        "document": "Пользователь прислал вопрос вместе с документом.",
        "audio": "Пользователь прислал вопрос вместе с аудио.",
        "voice": "Пользователь прислал вопрос голосовым сообщением.",
    }
    return mapping.get(content_type, "Пользователь прислал вопрос в необычном формате.")


def _build_question_answer_post(payload: dict, answer_text: str) -> str:
    question_text = (payload.get("question_text") or "").strip() or _fallback_question_text(payload)
    answer_text = answer_text.strip()
    author_line = "🤫 Анонимный вопрос" if payload.get("is_anonymous") else f"👤 Вопрос от {payload.get('author_name') or 'подписчика'}"
    parts = [
        "❓ *ВОПРОС ПОДПИСЧИКА*",
        _escape_markdown_v2(author_line),
        "",
        "*Вопрос*",
        _format_markdown_quote(question_text),
        "",
        "*Ответ администрации*",
        _format_markdown_quote(answer_text),
    ]

    tags = payload.get("public_tags") or []
    if tags:
        parts.extend(["", "*Теги*", _escape_markdown_v2(" ".join(tags))])

    return "\n".join(parts)


def _build_moderation_markup(*, is_album: bool = False, is_question: bool = False) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    approve_callback = "mod_album:approve" if is_album else "mod:approve"
    reject_callback = "mod_album:reject" if is_album else "mod:reject"
    approve_label = "Ответить и опубликовать" if is_question and not is_album else "Опубликовать"
    markup.add(types.InlineKeyboardButton(approve_label, callback_data=approve_callback))
    markup.add(types.InlineKeyboardButton("Отклонить", callback_data=reject_callback))
    return markup


def _preview_title(content: SubmissionContent, content_type: str) -> str:
    flags = []
    if content.is_question:
        flags.append("вопрос")
    if content.is_anonymous:
        flags.append("анон")
    flags.append(content_type)
    return "Новая запись: " + ", ".join(flags)


def _log_submission(message, content: SubmissionContent, *, event_type: str, content_type: str) -> None:
    log_event(
        event_type,
        bot="predlojka",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={
            "content_type": content_type,
            "anonymous": content.is_anonymous,
            "tags": content.public_tags,
        },
    )


def _send_admin_preview(message, content: SubmissionContent, publish_text: str) -> None:
    markup = _build_moderation_markup(is_question=content.is_question)
    preview_caption = publish_text or _compose_publish_text(content, _display_name(message.from_user))
    payload = {
        "content_type": message.content_type,
        "publish_text": publish_text,
        "file_id": None,
        "is_question": content.is_question,
        "helper_message_id": None,
        "source_user_id": message.from_user.id,
        "question_text": content.clean_text,
        "public_tags": list(content.public_tags),
        "is_anonymous": content.is_anonymous,
        "author_name": _display_name(message.from_user),
    }

    if message.content_type == "text":
        admin_message = predlojka_bot.send_message(
            admin,
            f"{_preview_title(content, message.content_type)}\n\n{preview_caption}",
            reply_markup=markup,
        )
    elif message.content_type == "sticker":
        payload["file_id"] = message.sticker.file_id
        admin_message = predlojka_bot.send_sticker(admin, message.sticker.file_id, reply_markup=markup)
        helper = predlojka_bot.send_message(admin, preview_caption, reply_to_message_id=admin_message.message_id)
        payload["helper_message_id"] = helper.message_id
    elif message.content_type == "photo":
        payload["file_id"] = message.photo[-1].file_id
        admin_message = predlojka_bot.send_photo(admin, message.photo[-1].file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "video":
        payload["file_id"] = message.video.file_id
        admin_message = predlojka_bot.send_video(admin, message.video.file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "document":
        payload["file_id"] = message.document.file_id
        admin_message = predlojka_bot.send_document(admin, message.document.file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "audio":
        payload["file_id"] = message.audio.file_id
        admin_message = predlojka_bot.send_audio(admin, message.audio.file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "voice":
        payload["file_id"] = message.voice.file_id
        admin_message = predlojka_bot.send_voice(admin, message.voice.file_id, caption=preview_caption, reply_markup=markup)
    else:
        raise ValueError(f"Неподдерживаемый тип контента: {message.content_type}")

    moderation_queue[admin_message.message_id] = payload


def _publish_payload(payload: dict) -> None:
    content_type = payload["content_type"]
    publish_text = payload["publish_text"]
    file_id = payload.get("file_id")

    if content_type == "text":
        predlojka_bot.send_message(channel, publish_text, disable_notification=True)
        return
    if content_type == "sticker":
        predlojka_bot.send_sticker(channel, file_id, disable_notification=True)
        if publish_text:
            predlojka_bot.send_message(channel, publish_text, disable_notification=True)
        return
    if content_type == "photo":
        predlojka_bot.send_photo(channel, file_id, caption=publish_text, disable_notification=True)
        return
    if content_type == "video":
        predlojka_bot.send_video(channel, file_id, caption=publish_text, disable_notification=True)
        return
    if content_type == "document":
        predlojka_bot.send_document(channel, file_id, caption=publish_text, disable_notification=True)
        return
    if content_type == "audio":
        predlojka_bot.send_audio(channel, file_id, caption=publish_text, disable_notification=True)
        return
    if content_type == "voice":
        predlojka_bot.send_voice(channel, file_id, caption=publish_text, disable_notification=True)
        return
    raise ValueError(f"Неподдерживаемый тип публикации: {content_type}")


def _publish_question_with_answer(payload: dict, answer_text: str) -> None:
    formatted_text = _build_question_answer_post(payload, answer_text)
    content_type = payload["content_type"]
    file_id = payload.get("file_id")

    if content_type == "text":
        predlojka_bot.send_message(channel, formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    if content_type == "photo":
        predlojka_bot.send_photo(channel, file_id, caption=formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    if content_type == "video":
        predlojka_bot.send_video(channel, file_id, caption=formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    if content_type == "document":
        predlojka_bot.send_document(channel, file_id, caption=formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    if content_type == "audio":
        predlojka_bot.send_audio(channel, file_id, caption=formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    if content_type == "voice":
        predlojka_bot.send_voice(channel, file_id, caption=formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    if content_type == "sticker":
        predlojka_bot.send_message(channel, formatted_text, disable_notification=True, parse_mode="MarkdownV2")
        return
    raise ValueError(f"Неподдерживаемый тип вопроса для публикации: {content_type}")


def _clear_preview_messages(payload: dict, moderation_message_id: int | None = None) -> None:
    helper_message_id = payload.get("helper_message_id")
    if helper_message_id:
        safe_delete_message(admin, helper_message_id)
    if moderation_message_id is not None:
        safe_delete_message(admin, moderation_message_id)


def _request_question_answer(call, payload: dict) -> None:
    pending_question_answers[call.from_user.id] = {
        "payload": payload,
        "moderation_message_id": call.message.message_id,
    }
    prompt = predlojka_bot.send_message(
        admin,
        "Отлично! Я рада, что ты заинтересовался) Напиши ответ текстиком, а я передам в канал! (^-^)\n\nЕсли всё же передумал, напиши /cancel_question_answer",
        reply_to_message_id=call.message.message_id,
    )
    predlojka_bot.register_next_step_handler(prompt, handle_question_answer_input)
    predlojka_bot.answer_callback_query(call.id, "Жду текст ответа.")
    log_event(
        "question_answer_requested",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )


def handle_question_answer_input(message):
    pending = pending_question_answers.get(message.from_user.id)
    if pending is None:
        predlojka_bot.reply_to(message, "Не могу найти вопроса, который ожидает ответа... (⊙▂⊙)")
        return

    if message.text and message.text.strip() == "/cancel_question_answer":
        payload = pending["payload"]
        moderation_queue[pending["moderation_message_id"]] = payload
        pending_question_answers.pop(message.from_user.id, None)
        predlojka_bot.reply_to(message, "Как скажешь, нет так нет! Вернула воспрос в очередь на модерацию.")
        return

    answer_text = (message.text or "").strip()
    if not answer_text:
        retry_prompt = predlojka_bot.reply_to(
            message,
            "Боюсь, я смогу принять только текст в качестве ответа... Увы (︶︹︶)",
        )
        predlojka_bot.register_next_step_handler(retry_prompt, handle_question_answer_input)
        return

    payload = pending["payload"]
    moderation_message_id = pending["moderation_message_id"]

    try:
        _publish_question_with_answer(payload, answer_text)
        _clear_preview_messages(payload, moderation_message_id)
        safe_delete_message(admin, message.message_id)
        pending_question_answers.pop(message.from_user.id, None)
        predlojka_bot.send_message(admin, "Вопрос с вашим прелестным ответом опубликован в канале! (｡•̀ᴗ-)✧")
        log_event(
            "question_approved",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"], "answer_length": len(answer_text)},
        )
        logger.info("Вопрос с ответом опубликован")
    except Exception as error:
        moderation_queue[moderation_message_id] = payload
        pending_question_answers.pop(message.from_user.id, None)
        logger.error(f"Ошибка при публикации вопроса с ответом: {error}")
        predlojka_bot.reply_to(message, "Не получилось опубликовать вопрос с ответом.. Вернула его в очередь модерации!")


def _handle_ai_request(message, content: SubmissionContent) -> None:
    name = _display_name(message.from_user)
    prompt_text = content.clean_text or message.text
    response_message = predlojka_bot.reply_to(message, "Думаю... (*￣3￣)╭")
    loop = None
    log_event("ai_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _get_ai_response() -> str:
            full_response = ""
            async for chunk in stream_ai(prompt_text, name):
                full_response = chunk
            return full_response

        full_text = loop.run_until_complete(_get_ai_response())
        predlojka_bot.edit_message_text(full_text, chat_id=message.chat.id, message_id=response_message.message_id)
        log_event("ai_completed", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)
    except Exception as error:
        logger.error(f"Ошибка в AI-запросе: {error}")
        log_event(
            "ai_failed",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"error": str(error)[:300]},
        )
        try:
            predlojka_bot.edit_message_text(
                "Извините, что-то пошло не так... Попробуй ещё раз позже (^_^;)",
                chat_id=message.chat.id,
                message_id=response_message.message_id,
            )
        except Exception:
            predlojka_bot.send_message(message.chat.id, "Извините, ошибка обработки...")
    finally:
        if loop is not None:
            loop.close()


def _submit_single_message(message) -> None:
    content_text = message.text if message.content_type == "text" else message.caption
    content = _parse_submission_text(content_text)

    if message.content_type == "text" and content.wants_ai and _can_use_ai(message.chat.id):
        _handle_ai_request(message, content)
        return

    if not _can_submit_post(message.chat.id):
        return

    user_name = _display_name(message.from_user)
    publish_text = _compose_publish_text(content, user_name)
    add_to_post_counter(message.from_user.id)

    predlojka_bot.send_message(
        message.chat.id,
        thx_for_message(user_name, mes_type="?" if content.is_question else "!"),
        reply_markup=q,
    )
    _send_admin_preview(message, content, publish_text)

    _log_submission(
        message,
        content,
        event_type="question_submitted" if content.is_question else "post_submitted",
        content_type=message.content_type,
    )
    logger.info(f"Получена запись для модерации: {message.content_type}")


@predlojka_bot.message_handler(content_types=["sticker", "text", "document", "audio", "voice"])
def accepter(message):
    if not user_exists(message.from_user.id):
        create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)

    if message.content_type == "text" and message.text.startswith("/"):
        predlojka_bot.reply_to(message, "Боюсь, такой команды я не знаю... (｡•́︿•̀｡)")
        return

    _submit_single_message(message)


def _build_album_media(items: list, publish_caption: str) -> list:
    media = []
    for index, item in enumerate(items):
        caption = publish_caption if index == 0 else None
        if item.content_type == "photo":
            media.append(types.InputMediaPhoto(item.photo[-1].file_id, caption=caption))
        elif item.content_type == "video":
            media.append(types.InputMediaVideo(item.video.file_id, caption=caption))
    return media


def process_media_group_for_moderation(media_group_id: str) -> None:
    try:
        items = media_groups_buffer.pop(media_group_id, [])
        media_groups_timer.pop(media_group_id, None)
        if not items:
            return
        if not _can_submit_post(items[0].chat.id):
            return

        user = items[0].from_user
        captions = [item.caption for item in items if item.caption]
        content = _parse_submission_text("\n".join(captions))
        user_name = _display_name(user)
        publish_caption = _compose_publish_text(content, user_name)
        media = _build_album_media(items, publish_caption)

        if not media:
            logger.error("Медиагруппа отклонена: нет поддерживаемых медиафайлов")
            return

        add_to_post_counter(user.id)
        predlojka_bot.send_message(
            items[0].chat.id,
            thx_for_message(user_name, mes_type="?" if content.is_question else "!"),
            reply_markup=q,
        )

        sent_preview = safe_send_media_group(admin, media)
        if not sent_preview:
            logger.error("Не удалось отправить альбом админу")
            return

        control_message = predlojka_bot.send_message(
            admin,
            f"{_preview_title(content, 'album')}\n\nМедиа: {len(media)}",
            reply_markup=_build_moderation_markup(is_album=True),
        )
        album_queue[control_message.message_id] = {
            "media": media,
            "preview_ids": [item.message_id for item in sent_preview],
            "is_question": content.is_question,
            "source_user_id": user.id,
        }
        log_event(
            "album_submitted",
            bot="predlojka",
            user_id=user.id,
            chat_id=items[0].chat.id,
            metadata={"count": len(media), "anonymous": content.is_anonymous, "tags": content.public_tags},
        )
        logger.info(f"Альбом {media_group_id} отправлен на модерацию")
    except Exception as error:
        logger.error(f"Критическая ошибка в process_media_group_for_moderation: {error}", exc_info=True)


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod_album:approve")
def accept_album(call):
    payload = album_queue.pop(call.message.message_id, None)
    if payload is None:
        r = "Этот альбом уже обработан или устарел."
        predlojka_bot.answer_callback_query(call.id, r)
        return

    sent = safe_send_media_group(channel, payload["media"])
    if not sent:
        album_queue[call.message.message_id] = payload
        predlojka_bot.answer_callback_query(call.id, "Не получилось опубликовать альбом.")
        return

    for preview_id in payload["preview_ids"]:
        safe_delete_message(admin, preview_id)
    safe_delete_message(admin, call.message.message_id)
    predlojka_bot.answer_callback_query(call.id, "Альбом опубликован!")
    log_event(
        "album_approved",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "is_question": payload["is_question"]},
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod_album:reject")
def reject_album(call):
    payload = album_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_bot.answer_callback_query(call.id, "Боюсь, этот альбом уже обработан или устарел... ")
        return

    for preview_id in payload["preview_ids"]:
        safe_delete_message(admin, preview_id)
    safe_delete_message(admin, call.message.message_id)
    predlojka_bot.answer_callback_query(call.id, "Альбом отклонён! (￣^￣)ゞ")
    log_event(
        "album_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "is_question": payload["is_question"]},
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:approve")
def sender(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_bot.answer_callback_query(call.id, "Эта запись уже обработана или устарела... (◔~◔)")
        return

    if payload["is_question"]:
        _request_question_answer(call, payload)
        return

    try:
        _publish_payload(payload)
        _clear_preview_messages(payload, call.message.message_id)
        predlojka_bot.answer_callback_query(call.id, "Сообщение опубликовано")
        log_event(
            "question_approved" if payload["is_question"] else "post_approved",
            bot="predlojka",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
        )
        logger.info("Пост опубликован")
    except Exception as error:
        moderation_queue[call.message.message_id] = payload
        logger.error(f"Ошибка в sender: {error}")
        predlojka_bot.answer_callback_query(call.id, "Ошибка при публикации")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:reject")
def denier(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_bot.answer_callback_query(call.id, "Эта запись уже обработана или устарела.")
        return

    _clear_preview_messages(payload, call.message.message_id)
    predlojka_bot.answer_callback_query(call.id, "Сообщение отклонено")
    log_event(
        "question_rejected" if payload["is_question"] else "post_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )
    logger.info("Пост отклонён")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("+album|"))
def accept_album_legacy(call):
    predlojka_bot.answer_callback_query(call.id, "Старая кнопка модерации больше не поддерживается. Перепроверь альбом заново.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("-album|"))
def reject_album_legacy(call):
    predlojka_bot.answer_callback_query(call.id, "Старая кнопка модерации больше не поддерживается.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("+") and not call.data.startswith("+album|"))
def sender_legacy(call):
    predlojka_bot.answer_callback_query(call.id, "Эта старая кнопка публикации уже неактивна.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("&"))
def st_sender_legacy(call):
    predlojka_bot.answer_callback_query(call.id, "Эта старая кнопка публикации уже неактивна.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "-")
def denier_legacy(call):
    predlojka_bot.answer_callback_query(call.id, "Эта старая кнопка модерации уже неактивна.")


@predlojka_bot.message_handler(content_types=["photo", "video"])
def media_group_handler(message):
    if not user_exists(message.from_user.id):
        create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)

    media_group_id = getattr(message, "media_group_id", None)
    if not media_group_id:
        _submit_single_message(message)
        return

    media_group_key = str(media_group_id)
    if media_group_key not in media_groups_buffer:
        media_groups_buffer[media_group_key] = []
    media_groups_buffer[media_group_key].append(message)

    timer = media_groups_timer.get(media_group_key)
    if timer is not None:
        timer.cancel()

    new_timer = threading.Timer(MEDIA_GROUP_TIMEOUT, process_media_group_for_moderation, args=(media_group_key,))
    media_groups_timer[media_group_key] = new_timer
    new_timer.start()
