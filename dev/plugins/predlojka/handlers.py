from __future__ import annotations

import logging
import asyncio
import inspect
from datetime import datetime
from pathlib import Path
import random

from aiogram import F, Router, types
from aiogram.filters import Command
from varibles.dialogue_loader import TEXT

from core.core_plugin.stats import log_event, log_command_usage
from database.scheduled_posts_db import create_scheduled_post
from database.sqlite_db import add_to_post_counter
from .classes import Post, PublishResult, MediaAttachment, MediaType, Platform, Post, PostAuthor, PostOrigin, PostTarget, PublishResult, PostFormatter
from plugins.ai.handlers import process_ai_message
from .service import thx_for_message
from database.scheduled_posts_db import list_scheduled_posts

from . import service as predlojka_service
from .service import (
    SubmissionContent,
    _build_platform_post_from_album,
    _build_platform_post_from_message,
    _build_service_text,
    _can_submit_post,
    _can_submit_service_message,
    _can_use_ai,
    _compose_publish_text,
    _deserialize_post,
    _display_name,
    _parse_submission_text,
    _serialize_post,
    ensure_post_author_exists,
    ensure_user_exists,
    safe_delete_message,
    safe_send_media_group,
    storage_user_id_for_post,
    _preview_scheduled_payload
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

q = types.ReplyKeyboardRemove()
media_groups_buffer: dict[str, list] = {}
media_groups_timer: dict[str, asyncio.Task] = {}
moderation_queue: dict[int, dict] = {}
album_queue: dict[int, dict] = {}
album_media_cache: dict[int, dict] = {}
pending_question_answers: dict[int, dict] = {}
direct_message_queue: dict[int, dict] = {}
pending_direct_message_answers: dict[int, dict] = {}
pending_scheduled_publications: dict[int, dict] = {}


telegram_admin_target = None
admin = None
predlojka_bot = None
channel = None
channel_red = None
chat_mishas_den = None
backup_chat = None
HIBERNATION = False
plugin_context = None
_registered_bot = None
_registered_router = None
QUESTION_ANSWER_SEPARATOR = "\n\n=====QUESTION_ANSWER_SEPARATOR=====\n\n"

MEDIA_GROUP_TIMEOUT = 2.0
BASE_DIR = Path(__file__).resolve().parents[2]
VARIBLES_DIR = BASE_DIR / "varibles"
EVENT_LIBRARY_PATH = VARIBLES_DIR / "events_library.txt"
REPORT_LIBRARY_PATH = VARIBLES_DIR / "reports_library.txt"


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _bot_call(method_name: str, *args, **kwargs):
    return await _maybe_await(getattr(predlojka_bot, method_name)(*args, **kwargs))


async def _sender_call(sender, method_name: str, *args, **kwargs):
    return await _maybe_await(getattr(sender, method_name)(*args, **kwargs))


def _configure_runtime(context) -> None:
    global plugin_context, predlojka_bot, telegram_admin_target
    global admin, channel, channel_red, chat_mishas_den, backup_chat, HIBERNATION

    plugin_context = context
    predlojka_bot = context.predlojka_bot
    telegram_admin_target = context.telegram_admin_target
    admin = context.admin_id
    channel = context.config.channel
    channel_red = context.config.channel_red
    chat_mishas_den = context.config.chat_mishas_den
    backup_chat = context.config.backup_chat
    HIBERNATION = context.config.HIBERNATION
    predlojka_service.configure(context)





async def _send_hibernation_message(chat_id: int, *, reply_to_message_id: int | None = None) -> None:
    await _bot_call(
        "send_message",
        chat_id,
        TEXT("hibernation_message"),
        reply_to_message_id=reply_to_message_id,
    )




async def publish_post(
        target,
        post: Post,
        rendered_text: str,
        *,
        disable_notification: bool = False,
        parse_mode: str | None = None,
    ):
        message_ids: list[int | str] = []
        effective_text, effective_parse_mode = predlojka_service._resolve_rendered_text(post, rendered_text, parse_mode)

        if post.is_album:
            media = predlojka_service._build_album_media(post, effective_text, effective_parse_mode)
            if not media:
                response = await _bot_call(
                    "send_message",
                    (target if isinstance(target, int) else target.destination_id),
                    effective_text,
                    disable_notification=disable_notification,
                    parse_mode=effective_parse_mode,
                )
                return PublishResult(target_id=(target if isinstance(target, int) else target.destination_id), message_ids=[response.message_id], raw_response=response)
            response = await _bot_call("send_media_group", (target if isinstance(target, int) else target.destination_id), media)
            message_ids.extend(item.message_id for item in response)
            return PublishResult(target_id=(target if isinstance(target, int) else target.destination_id), message_ids=message_ids, raw_response=response)

        if not post.attachments:
            response = await _bot_call(
                "send_message",
                (target if isinstance(target, int) else target.destination_id),
                effective_text,
                disable_notification=disable_notification,
                parse_mode=effective_parse_mode,
            )
            return PublishResult(target_id=(target if isinstance(target, int) else target.destination_id), message_ids=[response.message_id], raw_response=response)

        attachment = post.attachments[0]
        file_id = predlojka_service._resolve_telegram_reference(attachment)
        if not file_id:
            response = await _bot_call(
                "send_message",
                target.destination_id,
                effective_text,
                disable_notification=disable_notification,
                parse_mode=effective_parse_mode,
            )
            return PublishResult((target if isinstance(target, int) else target.destination_id), message_ids=[response.message_id], raw_response=response)

        if attachment.media_type == MediaType.STICKER:
            sticker_message = await _bot_call("send_sticker", target.destination_id, file_id, disable_notification=disable_notification)
            message_ids.append(sticker_message.message_id)
            if effective_text:
                text_message = await _bot_call(
                    "send_message",
                    target.destination_id,
                    effective_text,
                    disable_notification=disable_notification,
                    parse_mode=effective_parse_mode,
                )
                message_ids.append(text_message.message_id)
                return PublishResult(target_id=target.destination_id, message_ids=message_ids, raw_response=[sticker_message, text_message])
            return PublishResult(target_id=target.destination_id, message_ids=message_ids, raw_response=sticker_message)

        sender_map = {
            MediaType.PHOTO: predlojka_bot.send_photo,
            MediaType.VIDEO: predlojka_bot.send_video,
            MediaType.DOCUMENT: predlojka_bot.send_document,
            MediaType.AUDIO: predlojka_bot.send_audio,
            MediaType.VOICE: predlojka_bot.send_voice,
        }
        sender = sender_map.get(attachment.media_type)
        if sender is None:
            raise ValueError(f"Неподдерживаемый тип публикации в Telegram: {attachment.media_type.value}")

        response = await _maybe_await(sender(
            target.destination_id,
            file_id,
            caption=effective_text or None,
            disable_notification=disable_notification,
            parse_mode=effective_parse_mode,
        ))
        return PublishResult(target_id=target.destination_id, message_ids=[response.message_id], raw_response=response)






async def _maybe_send_advice(message, content: SubmissionContent) -> None:
    if content.ignore_reaction:
        return
    if random.random() >= 0.4:
        return
    await _bot_call(
        "send_message",
        message.chat.id,
        TEXT("advice_messages"),
        reply_to_message_id=message.message_id,
        parse_mode="HTML",
    )


async def _acknowledge_submission(message, content: SubmissionContent, user_name: str) -> None:
    if content.ignore_reaction:
        return

    if content.route == "event":
        text = thx_for_message(user_name, mes_type="event")
    elif content.route == "report":
        text = thx_for_message(user_name, mes_type="report")
    elif content.route == "message":
        text = thx_for_message(user_name, mes_type="message")
    else:
        text = thx_for_message(user_name, mes_type="?" if content.is_question else "!")

    sender = getattr(plugin_context, "tg_adapter", None) or predlojka_bot
    await _sender_call(sender, "send_message", message.chat.id, text, reply_markup=q)
    await _maybe_send_advice(message, content)


def _build_direct_message_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Ответить в ЛС", callback_data="dm:reply"))
    markup.add(types.InlineKeyboardButton("Закрыть", callback_data="dm:close"))
    return markup

def _author_line(message, content: SubmissionContent, user_name: str) -> str:
    if content.is_anonymous and content.route != "message":
        return "🤫 Автор: Аноним"
    username = getattr(message.from_user, "username", None)
    username_line = f" | @{username}" if username else ""
    return f"👤 Автор: {user_name}{username_line} | id {message.from_user.id}"


def _build_route_summary(message, content: SubmissionContent, user_name: str, *, route_label: str, content_type: str, items_count: int | None = None) -> str:
    lines = [
        route_label,
        _author_line(message, content, user_name),
        f"Тип контента: {content_type}",
    ]
    if items_count is not None:
        lines.append(f"Файлов в сообщении: {items_count}")
    if content.public_tags:
        lines.append("Публичные теги: " + " ".join(content.public_tags))
    if content.clean_text:
        lines.extend(["", content.clean_text])
    return "\n".join(lines)


def _append_library_entry(path: Path, message, content: SubmissionContent, user_name: str, *, route_label: str, content_type: str, items_count: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"[{timestamp}] {route_label}",
        _author_line(message, content, user_name),
        f"Тип контента: {content_type}",
    ]
    if items_count is not None:
        lines.append(f"Файлов в сообщении: {items_count}")
    if content.public_tags:
        lines.append("Публичные теги: " + " ".join(content.public_tags))
    lines.extend(["Текст:", content.clean_text or "(без текста)", "", "-" * 60, ""])
    with path.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines))


async def _send_report_library_snapshot() -> None:
    if not REPORT_LIBRARY_PATH.exists():
        return

    try:
        with REPORT_LIBRARY_PATH.open("rb") as file:
            await _bot_call(
                "send_document",
                backup_chat,
                file,
                visible_file_name="reports_library.txt",
                caption="Новый репорт добавлен в reports_library.txt",
                disable_notification=True,
            )
    except Exception as error:
        logger.error(f"Не удалось отправить reports_library.txt в debug chat: {error}")


async def _copy_single_message_to_admin(message):
    try:
        return await _bot_call("copy_message", admin, message.chat.id, message.message_id)
    except Exception as error:
        logger.error(f"Не удалось скопировать сообщение админу: {error}")
        return None


async def _store_special_route(message, content: SubmissionContent) -> None:
    user_name = _display_name(message.from_user)
    route_labels = {
        "event": "Новая идея события",
        "report": "Новый репорт",
        "message": "Новое сообщение админу",
    }
    route_label = route_labels[content.route]

    if content.route == "event":
        _append_library_entry(EVENT_LIBRARY_PATH, message, content, user_name, route_label=route_label, content_type=message.content_type)
    elif content.route == "report":
        _append_library_entry(REPORT_LIBRARY_PATH, message, content, user_name, route_label=route_label, content_type=message.content_type)
        await _send_report_library_snapshot()

    copied_message = await _copy_single_message_to_admin(message)
    summary = _build_route_summary(message, content, user_name, route_label=route_label, content_type=message.content_type)

    if content.route == "message":
        control_message = await _bot_call(
            "send_message",
            admin,
            summary,
            reply_to_message_id=copied_message.message_id if copied_message else None,
            reply_markup=_build_direct_message_markup(),
        )
        direct_message_queue[control_message.message_id] = {
            "source_user_id": message.from_user.id,
            "author_name": user_name,
            "is_anonymous": content.is_anonymous,
            "content_type": message.content_type,
        }
    else:
        await _bot_call(
            "send_message",
            admin,
            summary,
            reply_to_message_id=copied_message.message_id if copied_message else None,
        )

    await _acknowledge_submission(message, content, user_name)
    log_event(
        f"{content.route}_submitted",
        bot="predlojka",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"content_type": message.content_type, "anonymous": content.is_anonymous, "tags": content.public_tags},
    )


async def _store_special_route_album(items: list, content: SubmissionContent) -> None:
    first_item = items[0]
    user_name = _display_name(first_item.from_user)
    route_labels = {
        "event": "Новая идея события",
        "report": "Новый репорт",
        "message": "Новое сообщение админу",
    }
    route_label = route_labels[content.route]
    publish_caption = _build_service_text(content, user_name)
    media = _build_album_media(items, publish_caption)
    preview_ids: list[int] = []

    if content.route == "event":
        _append_library_entry(EVENT_LIBRARY_PATH, first_item, content, user_name, route_label=route_label, content_type="album", items_count=len(media))
    elif content.route == "report":
        _append_library_entry(REPORT_LIBRARY_PATH, first_item, content, user_name, route_label=route_label, content_type="album", items_count=len(media))
        await _send_report_library_snapshot()

    if media:
        sent_preview = await safe_send_media_group(admin, media)
        if sent_preview:
            preview_ids = [item.message_id for item in sent_preview]

    summary = _build_route_summary(first_item, content, user_name, route_label=route_label, content_type="album", items_count=len(media))
    if content.route == "message":
        control_message = await _bot_call(
            "send_message",
            admin,
            summary,
            reply_to_message_id=preview_ids[0] if preview_ids else None,
            reply_markup=_build_direct_message_markup(),
        )
        direct_message_queue[control_message.message_id] = {
            "source_user_id": first_item.from_user.id,
            "author_name": user_name,
            "is_anonymous": content.is_anonymous,
            "content_type": "album",
            "preview_ids": preview_ids,
        }
    else:
        await _bot_call("send_message", admin, summary, reply_to_message_id=preview_ids[0] if preview_ids else None)

    await _acknowledge_submission(first_item, content, user_name)
    log_event(
        f"{content.route}_submitted",
        bot="predlojka",
        user_id=first_item.from_user.id,
        chat_id=first_item.chat.id,
        metadata={"content_type": "album", "anonymous": content.is_anonymous, "tags": content.public_tags, "count": len(media)},
    )


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
    draft_callback = "mod_album:draft" if is_album else "mod:draft"
    schedule_callback = "mod_album:schedule" if is_album else "mod:schedule"
    approve_label = "Ответить и опубликовать" if is_question and not is_album else "Опубликовать"
    markup.add(types.InlineKeyboardButton(approve_label, callback_data=approve_callback))
    markup.add(types.InlineKeyboardButton("Отклонить", callback_data=reject_callback))
    markup.add(types.InlineKeyboardButton("В черновик", callback_data=draft_callback))
    markup.add(types.InlineKeyboardButton("Запланировать", callback_data=schedule_callback))
    return markup


def _preview_title_for_post(post: Post) -> str:
    flags = []
    if post.is_question:
        flags.append("question")
    if post.is_anonymous:
        flags.append("anon")
    flags.append(post.content_type_label)
    return "Новая запись: " + ", ".join(flags)


def _preview_title(content: SubmissionContent, content_type: str) -> str:
    flags = []
    if content.is_question:
        flags.append("question")
    if content.is_anonymous:
        flags.append("anon")
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


async def _send_admin_preview(message, content: SubmissionContent, publish_text: str) -> None:
    markup = _build_moderation_markup(is_question=content.is_question)
    platform_post = _build_platform_post_from_message(message, content)
    preview_caption = publish_text or _compose_publish_text(content, _display_name(message.from_user))
    preview_formatted_text = PostFormatter.compose_publish_html(platform_post) if platform_post.text_parse_mode == "HTML" else preview_caption
    preview_parse_mode = "HTML" if platform_post.text_parse_mode == "HTML" else None
    payload = {
        "content_type": message.content_type,
        "publish_text": publish_text,
        "file_id": None,
        "is_question": content.is_question,
        "helper_message_id": None,
        "preview_message_ids": [],
        "source_user_id": message.from_user.id,
        "question_text": content.clean_text,
        "public_tags": list(content.public_tags),
        "is_anonymous": content.is_anonymous,
        "author_name": _display_name(message.from_user),
        "post_data": _serialize_post(platform_post),
    }

    if message.content_type == "text":
        admin_message = await _bot_call(
            "send_message",
            admin,
            f"{_preview_title(content, message.content_type)}\n\n{preview_formatted_text}",
            reply_markup=markup,
            parse_mode=preview_parse_mode,
        )
    elif message.content_type == "sticker":
        payload["file_id"] = message.sticker.file_id
        admin_message = await _bot_call("send_sticker", admin, message.sticker.file_id, reply_markup=markup)
        helper = await _bot_call("send_message", admin, preview_formatted_text, reply_to_message_id=admin_message.message_id, parse_mode=preview_parse_mode)
        payload["helper_message_id"] = helper.message_id
    elif message.content_type == "photo":
        payload["file_id"] = message.photo[-1].file_id
        admin_message = await _bot_call("send_photo", admin, message.photo[-1].file_id, caption=preview_formatted_text, reply_markup=markup, parse_mode=preview_parse_mode)
    elif message.content_type == "video":
        payload["file_id"] = message.video.file_id
        admin_message = await _bot_call("send_video", admin, message.video.file_id, caption=preview_formatted_text, reply_markup=markup, parse_mode=preview_parse_mode)
    elif message.content_type == "document":
        payload["file_id"] = message.document.file_id
        admin_message = await _bot_call("send_document", admin, message.document.file_id, caption=preview_formatted_text, reply_markup=markup, parse_mode=preview_parse_mode)
    elif message.content_type == "audio":
        payload["file_id"] = message.audio.file_id
        admin_message = await _bot_call("send_audio", admin, message.audio.file_id, caption=preview_formatted_text, reply_markup=markup, parse_mode=preview_parse_mode)
    elif message.content_type == "voice":
        payload["file_id"] = message.voice.file_id
        admin_message = await _bot_call("send_voice", admin, message.voice.file_id, caption=preview_formatted_text, reply_markup=markup, parse_mode=preview_parse_mode)
    else:
        raise ValueError(f"Неподдерживаемый тип контента: {message.content_type}")

    moderation_queue[admin_message.message_id] = payload


async def _send_external_admin_preview(post: Post) -> None:
    preview_text = PostFormatter.compose_publish_text(post)
    preview_result = await publish_post(telegram_admin_target, post, preview_text)
    control_message = await _bot_call(
        "send_message",
        admin,
        _preview_title_for_post(post),
        reply_markup=_build_moderation_markup(is_question=post.is_question),
    )
    moderation_queue[control_message.message_id] = {
        "content_type": post.content_type_label,
        "publish_text": preview_text,
        "file_id": None,
        "is_question": post.is_question,
        "helper_message_id": None,
        "preview_message_ids": [int(message_id) for message_id in preview_result.message_ids],
        "source_user_id": storage_user_id_for_post(post),
        "question_text": post.text,
        "public_tags": list(post.public_tags),
        "is_anonymous": post.is_anonymous,
        "author_name": post.author.display_name,
        "post_data": _serialize_post(post),
    }


async def _notify_publish_warnings(errors: dict) -> None:
    if not errors:
        return
    warning_text = "Часть площадок не приняла публикацию:\n" + "\n".join(f"- {error}" for error in errors.values())
    await _bot_call("send_message", admin, warning_text)


async def _publish_payload(payload: dict) -> None:
    content_type = payload["content_type"]
    publish_text = payload["publish_text"]
    file_id = payload.get("file_id")
    parse_mode = payload.get("parse_mode")
    post_data = payload.get("post_data")

    if post_data:
        try:
            await publish_post(
                target=channel,
                post=_deserialize_post(post_data),
                rendered_text=publish_text,
                disable_notification=True,
                parse_mode=parse_mode,
            )
        except Exception as e:
            await _notify_publish_warnings(e)
        return

    if content_type == "text":
        await _bot_call("send_message", channel, publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "sticker":
        await _bot_call("send_sticker", channel, file_id, disable_notification=True)
        if publish_text:
            await _bot_call("send_message", channel, publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "photo":
        await _bot_call("send_photo", channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "video":
        await _bot_call("send_video", channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "document":
        await _bot_call("send_document", channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "audio":
        await _bot_call("send_audio", channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "voice":
        await _bot_call("send_voice", channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    raise ValueError(f"Неподдерживаемый тип публикации: {content_type}")


def _serialize_album_media(items: list, publish_caption: str) -> list[dict]:
    media: list[dict] = []
    for index, item in enumerate(items):
        caption = publish_caption if index == 0 else None
        if item.content_type == "photo":
            media.append({"content_type": "photo", "file_id": item.photo[-1].file_id, "caption": caption})
        elif item.content_type == "video":
            media.append({"content_type": "video", "file_id": item.video.file_id, "caption": caption})
    return media


def _deserialize_album_media(media_items: list[dict]) -> list:
    media = []
    for item in media_items:
        if item["content_type"] == "photo":
            media.append(types.InputMediaPhoto(item["file_id"], caption=item.get("caption")))
        elif item["content_type"] == "video":
            media.append(types.InputMediaVideo(item["file_id"], caption=item.get("caption")))
        else:
            raise ValueError(f"Неподдерживаемый элемент альбома: {item['content_type']}")
    return media


async def _publish_album_payload(payload: dict) -> None:
    post_data = payload.get("post_data")
    if post_data:
        outcome = await publish_post(
            target=channel,
            post=_deserialize_post(post_data),
            rendered_text=payload.get("publish_text", ""),
            disable_notification=True,
            parse_mode=payload.get("parse_mode"),
        )
        if outcome.has_errors:
            await _notify_publish_warnings(outcome.errors)
        return
    media = _deserialize_album_media(payload["media"])
    sent = await safe_send_media_group(channel, media)
    if not sent:
        raise RuntimeError("Не удалось отправить альбом в канал")


def _build_question_answer_bundle(payload: dict, answer_text: str) -> str:
    question_text = (payload.get("question_text") or "").strip() or _fallback_question_text(payload)
    return f"{question_text}{QUESTION_ANSWER_SEPARATOR}{answer_text.strip()}"


def _build_ready_question_payload(payload: dict, answer_text: str) -> dict:
    ready_payload = dict(payload)
    answer_text = answer_text.strip()
    ready_payload["question_answer_bundle"] = _build_question_answer_bundle(payload, answer_text)
    if ready_payload.get("post_data"):
        ready_payload["publish_text"] = PostFormatter.build_question_answer_post(_deserialize_post(ready_payload["post_data"]), answer_text)
    else:
        ready_payload["publish_text"] = _build_question_answer_post(payload, answer_text)
    ready_payload["parse_mode"] = "MarkdownV2"

    return ready_payload


async def _publish_question_with_answer(payload: dict, answer_text: str) -> None:
    await _publish_payload(_build_ready_question_payload(payload, answer_text))


async def _clear_preview_messages(payload: dict, moderation_message_id: int | None = None) -> None:
    helper_message_id = payload.get("helper_message_id")
    if helper_message_id:
        await safe_delete_message(admin, helper_message_id)
    for preview_message_id in payload.get("preview_message_ids", []):
        await safe_delete_message(admin, preview_message_id)
    if moderation_message_id is not None:
        await safe_delete_message(admin, moderation_message_id)


async def _clear_album_preview(queue_payload: dict, moderation_message_id: int | None = None) -> None:
    for preview_id in queue_payload.get("preview_ids", []):
        await safe_delete_message(admin, preview_id)
    if moderation_message_id is not None:
        await safe_delete_message(admin, moderation_message_id)


def _parse_schedule_datetime(raw_value: str) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None

    now = datetime.now()
    formats = (
        ("%d.%m.%Y %H:%M", False),
        ("%d.%m.%y %H:%M", False),
        ("%Y-%m-%d %H:%M", False),
        ("%d.%m %H:%M", True),
    )

    for fmt, inject_year in formats:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if inject_year:
            parsed = parsed.replace(year=now.year)
        return parsed
    return None


async def _request_schedule_datetime(admin_user_id: int, pending_payload: dict, *, reply_to_message_id: int | None = None, callback_query_id: str | None = None) -> None:
    pending_scheduled_publications[admin_user_id] = pending_payload
    await _bot_call(
        "send_message",
        admin,
        "Напиши дату и время публикации.\n\nПоддерживаю форматы: ДД.ММ.ГГГГ ЧЧ:ММ, ДД.ММ ЧЧ:ММ или ГГГГ-ММ-ДД ЧЧ:ММ.\nДля отмены отправь /cancel_schedule",
        reply_to_message_id=reply_to_message_id,
    )
    if callback_query_id is not None:
        await _bot_call("answer_callback_query", callback_query_id, "Жду дату и время публикации.")


async def _save_single_payload_as_draft(payload: dict, moderation_message_id: int, admin_user_id: int, chat_id: int) -> None:
    record_id = create_scheduled_post(
        payload=dict(payload),
        content_type=payload["content_type"],
        publish_at=None,
        is_question=payload["is_question"],
        is_anonymous=payload["is_anonymous"],
        source_user_id=payload["source_user_id"],
        status="draft",
        created_by=admin_user_id,
    )
    await _clear_preview_messages(payload, moderation_message_id)
    await _bot_call("send_message", admin, f"Черновик сохранён. ID задачи: {record_id}")
    log_event(
        "post_drafted",
        bot="predlojka",
        user_id=admin_user_id,
        chat_id=chat_id,
        metadata={
            "draft_id": record_id,
            "source_user_id": payload["source_user_id"],
            "content_type": payload["content_type"],
        },
    )


async def _save_album_payload_as_draft(queue_payload: dict, storage_payload: dict, moderation_message_id: int, admin_user_id: int, chat_id: int) -> None:
    record_id = create_scheduled_post(
        payload=dict(storage_payload),
        content_type="album",
        publish_at=None,
        is_question=queue_payload["is_question"],
        is_anonymous=queue_payload["is_anonymous"],
        source_user_id=queue_payload["source_user_id"],
        status="draft",
        created_by=admin_user_id,
    )
    await _clear_album_preview(queue_payload, moderation_message_id)
    await _bot_call("send_message", admin, f"Черновик альбома сохранён. ID задачи: {record_id}")
    log_event(
        "album_drafted",
        bot="predlojka",
        user_id=admin_user_id,
        chat_id=chat_id,
        metadata={
            "draft_id": record_id,
            "source_user_id": queue_payload["source_user_id"],
            "is_question": queue_payload["is_question"],
        },
    )


def _restore_scheduled_pending(pending: dict) -> None:
    moderation_message_id = pending["moderation_message_id"]
    if pending["queue_type"] == "album":
        album_queue[moderation_message_id] = pending["queue_payload"]
        album_media_cache[moderation_message_id] = pending["storage_payload"]
    else:
        moderation_queue[moderation_message_id] = pending["storage_payload"]


async def handle_schedule_datetime_input(message):
    pending = pending_scheduled_publications.get(message.from_user.id)
    if pending is None:
        await _maybe_await(message.reply("Не вижу публикации, которая ждёт планирования."))
        return

    if message.text and message.text.strip() == "/cancel_schedule":
        _restore_scheduled_pending(pending)
        pending_scheduled_publications.pop(message.from_user.id, None)
        await _maybe_await(message.reply("Отменяю планирование и возвращаю запись в очередь модерации."))
        return

    publish_at = _parse_schedule_datetime(message.text or "")
    if publish_at is None:
        await _maybe_await(message.reply(
            "Не смогла распознать дату. Попробуй формат вроде 05.04.2026 14:30.",
        ))
        return

    if publish_at <= datetime.now():
        await _maybe_await(message.reply(
            "Нужно указать время в будущем. Попробуй ещё раз.",
        ))
        return

    try:
        record_id = create_scheduled_post(
            payload=pending["storage_payload"],
            content_type=pending["content_type"],
            publish_at=publish_at,
            is_question=pending["is_question"],
            is_anonymous=pending["is_anonymous"],
            source_user_id=pending["source_user_id"],
            created_by=message.from_user.id,
        )
        if pending["queue_type"] == "album":
            await _clear_album_preview(pending["queue_payload"], pending["moderation_message_id"])
        else:
            await _clear_preview_messages(pending["storage_payload"], pending["moderation_message_id"])
        await safe_delete_message(admin, message.message_id)
        pending_scheduled_publications.pop(message.from_user.id, None)
        await _bot_call(
            "send_message",
            admin,
            f"Публикацию запланировала на {publish_at.strftime('%d.%m.%Y %H:%M')}.\nID задачи: {record_id}",
        )
        log_event(
            "post_scheduled",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={
                "schedule_id": record_id,
                "publish_at": publish_at.strftime("%Y-%m-%d %H:%M:%S"),
                "content_type": pending["content_type"],
                "source_user_id": pending["source_user_id"],
            },
        )
    except Exception as error:
        _restore_scheduled_pending(pending)
        pending_scheduled_publications.pop(message.from_user.id, None)
        logger.error(f"Не удалось сохранить отложенную публикацию: {error}")
        await _maybe_await(message.reply("Не получилось сохранить публикацию. Вернула её в очередь модерации."))


async def _request_question_answer(call, payload: dict) -> None:
    pending_question_answers[call.from_user.id] = {
        "payload": payload,
        "moderation_message_id": call.message.message_id,
        "action": "publish",
    }
    await _bot_call(
        "send_message",
        admin,
        # TODO: Убрать этот диалог в texts.json
        "Отлично! Я рада, что ты заинтересовался) Напиши ответ текстиком, а я передам в канал! (^-^)\n\nЕсли всё же передумал, напиши /cancel_question_answer",
        reply_to_message_id=call.message.message_id,
    )
    await _bot_call("answer_callback_query", call.id, "Жду текст ответа.")
    log_event(
        "question_answer_requested",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )


async def _request_question_answer_for_action(call, payload: dict, action: str) -> None:
    pending_question_answers[call.from_user.id] = {
        "payload": payload,
        "moderation_message_id": call.message.message_id,
        "action": action,
    }
    action_text = {
        "publish": "опубликую",
        "schedule": "подготовлю к отложенной публикации",
        "draft": "сохраню в черновик",
    }[action]
    await _bot_call(
        "send_message",
        admin,
        f"Напиши ответ текстом, и я {action_text} вопрос одним готовым постом.\n\nЕсли передумал, напиши /cancel_question_answer",
        reply_to_message_id=call.message.message_id,
    )
    await _bot_call("answer_callback_query", call.id, "Жду текст ответа.")


async def handle_question_answer_input(message):
    pending = pending_question_answers.get(message.from_user.id)
    if pending is None:
        await _maybe_await(message.reply("Не могу найти вопроса, который ожидает ответа... (⊙▂⊙)"))
        return

    if message.text and message.text.strip() == "/cancel_question_answer":
        payload = pending["payload"]
        moderation_queue[pending["moderation_message_id"]] = payload
        pending_question_answers.pop(message.from_user.id, None)
        await _maybe_await(message.reply("Как скажешь, нет так нет! Вернула воспрос в очередь на модерацию."))
        return

    answer_text = (message.text or "").strip()
    if not answer_text:
        await _maybe_await(message.reply(
            "Боюсь, я смогу принять только текст в качестве ответа... Увы (︶︹︶)",
        ))
        return

    payload = pending["payload"]
    moderation_message_id = pending["moderation_message_id"]
    action = pending.get("action", "publish")
    ready_payload = _build_ready_question_payload(payload, answer_text)

    try:
        if action == "publish":
            await _publish_payload(ready_payload)
            await _clear_preview_messages(ready_payload, moderation_message_id)
            await safe_delete_message(admin, message.message_id)
            pending_question_answers.pop(message.from_user.id, None)
            await _bot_call("send_message", admin, "Вопрос с вашим прелестным ответом опубликован в канале! (｡•̀ᴗ-)✧")
            log_event(
                "question_approved",
                bot="predlojka",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"source_user_id": payload["source_user_id"], "content_type": ready_payload["content_type"], "answer_length": len(answer_text)},
            )
            logger.info("Вопрос с ответом опубликован")
            return

        if action == "draft":
            await _save_single_payload_as_draft(ready_payload, moderation_message_id, message.from_user.id, message.chat.id)
            await safe_delete_message(admin, message.message_id)
            pending_question_answers.pop(message.from_user.id, None)
            return

        if action == "schedule":
            pending_question_answers.pop(message.from_user.id, None)
            await safe_delete_message(admin, message.message_id)
            pending_payload = {
                "queue_type": "single",
                "queue_payload": None,
                "storage_payload": ready_payload,
                "content_type": ready_payload["content_type"],
                "is_question": ready_payload["is_question"],
                "is_anonymous": ready_payload["is_anonymous"],
                "source_user_id": ready_payload["source_user_id"],
                "moderation_message_id": moderation_message_id,
            }
            await _request_schedule_datetime(
                message.from_user.id,
                pending_payload,
                reply_to_message_id=moderation_message_id,
            )
            return

        raise ValueError(f"Неизвестное действие для вопроса: {action}")
    except Exception as error:
        moderation_queue[moderation_message_id] = payload
        pending_question_answers.pop(message.from_user.id, None)
        logger.error(f"Ошибка при публикации вопроса с ответом: {error}")
        await _maybe_await(message.reply("Не получилось обработать вопрос с ответом. Вернула его в очередь модерации!"))


async def _request_direct_message_answer(call, payload: dict) -> None:
    pending_direct_message_answers[call.from_user.id] = {
        "payload": payload,
        "control_message_id": call.message.message_id,
    }
    await _bot_call(
        "send_message",
        admin,
        "Напиши текст ответа, и я отправлю его пользователю в ЛС.\n\nЕсли передумал, напиши /cancel_dm_answer",
        reply_to_message_id=call.message.message_id,
    )
    await _bot_call("answer_callback_query", call.id, "Жду ответ для отправки в ЛС.")


async def handle_direct_message_answer_input(message):
    pending = pending_direct_message_answers.get(message.from_user.id)
    if pending is None:
        await _maybe_await(message.reply("Не вижу сообщения, которое ждёт ответа."))
        return

    if message.text and message.text.strip() == "/cancel_dm_answer":
        direct_message_queue[pending["control_message_id"]] = pending["payload"]
        pending_direct_message_answers.pop(message.from_user.id, None)
        await _maybe_await(message.reply("Хорошо, отменяю ответ и возвращаю сообщение в очередь."))
        return

    answer_text = (message.text or "").strip()
    if not answer_text:
        await _maybe_await(message.reply("Смогу переслать пользователю только текстовый ответ."))
        return

    payload = pending["payload"]
    control_message_id = pending["control_message_id"]

    try:
        await _bot_call(
            "send_message",
            payload["source_user_id"],
            "Ответ администрации:\n\n" + answer_text,
        )
        pending_direct_message_answers.pop(message.from_user.id, None)
        await safe_delete_message(admin, control_message_id)
        await safe_delete_message(admin, message.message_id)
        await _bot_call("send_message", admin, "Ответ пользователю отправлен в ЛС.")
        log_event(
            "direct_message_replied",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"source_user_id": payload["source_user_id"], "answer_length": len(answer_text)},
        )
    except Exception as error:
        direct_message_queue[control_message_id] = payload
        pending_direct_message_answers.pop(message.from_user.id, None)
        logger.error(f"Не удалось отправить ответ в ЛС: {error}")
        await _maybe_await(message.reply("Не получилось отправить ответ в ЛС. Вернула сообщение в очередь."))


async def _submit_single_message(message) -> None:
    content_text = message.text if message.content_type == "text" else message.caption
    content = _parse_submission_text(content_text)

    if HIBERNATION and message.chat.id not in [chat_mishas_den, channel, channel_red]:
        await _send_hibernation_message(message.chat.id, reply_to_message_id=message.message_id)
        return

    if content.ignore_reaction:
        return

    if content.route == "post" and message.content_type == "text" and content.wants_ai and _can_use_ai(message.chat.id):
        if plugin_context is None:
            logger.error("AI-запрос нельзя обработать: PredlojkaPlugin не получил AppContext.")
            await _maybe_await(message.reply("AI сейчас не подключён. Попробуй чуть позже."))
            return
        await process_ai_message(plugin_context, message, content)
        return

    if content.route == "post" and not _can_submit_post(message.chat.id):
        return

    if content.route != "post" and not _can_submit_service_message(message.chat.id):
        return

    user_name = _display_name(message.from_user)

    if content.route != "post":
        await _store_special_route(message, content)
        return

    publish_text = _compose_publish_text(content, user_name)
    add_to_post_counter(message.from_user.id)
    await _acknowledge_submission(message, content, user_name)
    await _send_admin_preview(message, content, publish_text)

    _log_submission(
        message,
        content,
        event_type="question_submitted" if content.is_question else "post_submitted",
        content_type=message.content_type,
    )
    logger.info(f"Получена запись для модерации: {message.content_type}")


async def accepter(message):
    ensure_user_exists(message.from_user)

    # if message.content_type == "text" and message.text.startswith("/"):
    #     predlojka_bot.reply_to(message, "Боюсь, такой команды я не знаю... (｡•́︿•̀｡)")
    #     return

    await _submit_single_message(message)


def _build_album_media(items: list, publish_caption: str) -> list:
    return _deserialize_album_media(_serialize_album_media(items, publish_caption))


async def process_media_group_for_moderation(media_group_id: str) -> None:
    try:
        items = media_groups_buffer.pop(media_group_id, [])
        media_groups_timer.pop(media_group_id, None)
        if not items:
            return

        user = items[0].from_user
        captions = [item.caption for item in items if item.caption]
        content = _parse_submission_text("\n".join(captions))
        if HIBERNATION:
            await _send_hibernation_message(items[0].chat.id, reply_to_message_id=items[0].message_id)
            return
        if content.ignore_reaction:
            return
        if content.route == "post" and not _can_submit_post(items[0].chat.id):
            return
        if content.route != "post" and not _can_submit_service_message(items[0].chat.id):
            return

        if content.route != "post":
            await _store_special_route_album(items, content)
            return

        user_name = _display_name(user)
        publish_caption = _compose_publish_text(content, user_name)
        platform_post = _build_platform_post_from_album(items, content)
        serialized_media = _serialize_album_media(items, publish_caption)
        media = _deserialize_album_media(serialized_media)

        if not media:
            logger.error("Медиагруппа отклонена: нет поддерживаемых медиафайлов")
            return

        add_to_post_counter(user.id)
        await _acknowledge_submission(items[0], content, user_name)

        sent_preview = await safe_send_media_group(admin, media)
        if not sent_preview:
            logger.error("Не удалось отправить альбом админу")
            return

        control_message = await _bot_call(
            "send_message",
            admin,
            f"{_preview_title(content, 'album')}\n\nМедиа: {len(media)}",
            reply_markup=_build_moderation_markup(is_album=True),
        )
        album_queue[control_message.message_id] = {
            "preview_ids": [item.message_id for item in sent_preview],
            "is_question": content.is_question,
            "is_anonymous": content.is_anonymous,
            "source_user_id": user.id,
        }
        album_media_cache[control_message.message_id] = {
            "media": serialized_media,
            "publish_text": publish_caption,
            "post_data": _serialize_post(platform_post),
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


async def accept_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    media_payload = album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None or media_payload is None:
        if queue_payload is not None:
            album_queue[call.message.message_id] = queue_payload
        if media_payload is not None:
            album_media_cache[call.message.message_id] = media_payload
        r = "Этот альбом уже обработан или устарел."
        await _bot_call("answer_callback_query", call.id, r)
        return

    try:
        await _publish_album_payload(media_payload)
    except Exception as error:
        album_queue[call.message.message_id] = queue_payload
        album_media_cache[call.message.message_id] = media_payload
        logger.error(f"Ошибка при публикации альбома: {error}")
        await _bot_call("answer_callback_query", call.id, "Не получилось опубликовать альбом.")
        return

    await _clear_album_preview(queue_payload, call.message.message_id)
    await _bot_call("answer_callback_query", call.id, "Альбом опубликован!")
    log_event(
        "album_approved",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": queue_payload["source_user_id"], "is_question": queue_payload["is_question"]},
    )


async def reject_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None:
        await _bot_call("answer_callback_query", call.id, "Боюсь, этот альбом уже обработан или устарел... ")
        return

    await _clear_album_preview(queue_payload, call.message.message_id)
    await _bot_call("answer_callback_query", call.id, "Альбом отклонён! (￣^￣)ゞ")
    log_event(
        "album_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": queue_payload["source_user_id"], "is_question": queue_payload["is_question"]},
    )


async def draft_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    storage_payload = album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None or storage_payload is None:
        if queue_payload is not None:
            album_queue[call.message.message_id] = queue_payload
        if storage_payload is not None:
            album_media_cache[call.message.message_id] = storage_payload
        await _bot_call("answer_callback_query", call.id, "Этот альбом уже обработан или устарел.")
        return

    await _save_album_payload_as_draft(queue_payload, storage_payload, call.message.message_id, call.from_user.id, call.message.chat.id)
    await _bot_call("answer_callback_query", call.id, "Альбом сохранён в черновиках.")


async def schedule_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    media_payload = album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None or media_payload is None:
        if queue_payload is not None:
            album_queue[call.message.message_id] = queue_payload
        if media_payload is not None:
            album_media_cache[call.message.message_id] = media_payload
        await _bot_call("answer_callback_query", call.id, "Этот альбом уже обработан или устарел.")
        return

    pending_payload = {
        "queue_type": "album",
        "queue_payload": queue_payload,
        "storage_payload": media_payload,
        "content_type": "album",
        "is_question": queue_payload["is_question"],
        "is_anonymous": queue_payload["is_anonymous"],
        "source_user_id": queue_payload["source_user_id"],
        "moderation_message_id": call.message.message_id,
    }
    await _request_schedule_datetime(
        call.from_user.id,
        pending_payload,
        reply_to_message_id=call.message.message_id,
        callback_query_id=call.id,
    )


async def sender(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        await _bot_call("answer_callback_query", call.id, "Эта запись уже обработана или устарела... (◔~◔)")
        return

    if payload["is_question"] and not payload.get("question_answer_bundle"):
        await _request_question_answer(call, payload)
        return

    try:
        await _publish_payload(payload)
        await _clear_preview_messages(payload, call.message.message_id)
        await _bot_call("answer_callback_query", call.id, "Сообщение опубликовано")
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
        await _bot_call("answer_callback_query", call.id, "Ошибка при публикации")


async def denier(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        await _bot_call("answer_callback_query", call.id, "Эта запись уже обработана или устарела.")
        return

    await _clear_preview_messages(payload, call.message.message_id)
    await _bot_call("answer_callback_query", call.id, "Сообщение отклонено")
    log_event(
        "question_rejected" if payload["is_question"] else "post_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )
    logger.info("Пост отклонён")


async def draft_single_post(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        await _bot_call("answer_callback_query", call.id, "Эта запись уже обработана или устарела.")
        return

    if payload["is_question"] and not payload.get("question_answer_bundle"):
        await _request_question_answer_for_action(call, payload, "draft")
        return

    await _save_single_payload_as_draft(payload, call.message.message_id, call.from_user.id, call.message.chat.id)
    await _bot_call("answer_callback_query", call.id, "Запись сохранена в черновиках.")


async def schedule_single_post(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        await _bot_call("answer_callback_query", call.id, "Эта запись уже обработана или устарела.")
        return

    if payload["is_question"] and not payload.get("question_answer_bundle"):
        await _request_question_answer_for_action(call, payload, "schedule")
        return

    pending_payload = {
        "queue_type": "single",
        "queue_payload": None,
        "storage_payload": dict(payload),
        "content_type": payload["content_type"],
        "is_question": payload["is_question"],
        "is_anonymous": payload["is_anonymous"],
        "source_user_id": payload["source_user_id"],
        "moderation_message_id": call.message.message_id,
    }
    await _request_schedule_datetime(
        call.from_user.id,
        pending_payload,
        reply_to_message_id=call.message.message_id,
        callback_query_id=call.id,
    )


async def reply_in_dm(call):
    payload = direct_message_queue.pop(call.message.message_id, None)
    if payload is None:
        await _bot_call("answer_callback_query", call.id, "Это сообщение уже обработано или устарело.")
        return
    await _request_direct_message_answer(call, payload)


async def close_dm_message(call):
    payload = direct_message_queue.pop(call.message.message_id, None)
    if payload is None:
        await _bot_call("answer_callback_query", call.id, "Это сообщение уже закрыто или устарело.")
        return
    await safe_delete_message(admin, call.message.message_id)
    await _bot_call("answer_callback_query", call.id, "Сообщение закрыто.")
    log_event(
        "direct_message_closed",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )


async def publish_due_scheduled_posts() -> None:
    from .jobs import publish_due_scheduled_posts as run_job

    await run_job()

async def show_scheduled_posts(message):
    if message.from_user.id != admin:
        return

    log_command_usage("predlojka", "scheduled_posts", message)
    rows = list_scheduled_posts(limit=30)

    if not rows:
        await _maybe_await(message.reply("В `scheduled_posts` пока пусто: ни черновиков, ни отложек нет.", parse_mode="Markdown"))
        return

    lines = ["Содержимое `scheduled_posts`:\n"]
    for row in rows:
        status_label = "Запланировано" if row["status"] == "scheduled" else "Черновик"
        publish_at = row.get("publish_at") or "без даты"
        content_type = row.get("content_type") or "unknown"
        source_user_id = row.get("source_user_id")
        preview = _preview_scheduled_payload(row.get("payload") or {}, content_type)
        lines.append(
            f"#{row['doc_id']} | {status_label} | {content_type} | {publish_at} | user {source_user_id}\n{preview}\n"
        )

    await _maybe_await(message.reply("\n".join(lines), parse_mode="Markdown"))

async def _submit_external_post_async(post: Post, *, acknowledge_callback=None) -> None:
    storage_user_id = ensure_post_author_exists(post)
    add_to_post_counter(storage_user_id)

    if acknowledge_callback is not None:
        acknowledge_callback(post)

    await _send_external_admin_preview(post)
    log_event(
        "question_submitted" if post.is_question else "post_submitted",
        bot="predlojka",
        user_id=storage_user_id,
        chat_id=int(post.origin.chat_id),
        metadata={
            "source_platform": post.origin.platform.value,
            "content_type": post.content_type_label,
            "anonymous": post.is_anonymous,
            "tags": post.public_tags,
        },
    )
    logger.info(f"Получена запись для модерации: {post.content_type_label} ({post.origin.platform.value})")


def submit_external_post(post: Post, *, acknowledge_callback=None) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_submit_external_post_async(post, acknowledge_callback=acknowledge_callback))
        return
    loop.create_task(_submit_external_post_async(post, acknowledge_callback=acknowledge_callback))


async def media_group_handler(message):
    ensure_user_exists(message.from_user)

    media_group_id = getattr(message, "media_group_id", None)
    if not media_group_id:
        await _submit_single_message(message)
        return

    media_group_key = str(media_group_id)
    if media_group_key not in media_groups_buffer:
        media_groups_buffer[media_group_key] = []
    media_groups_buffer[media_group_key].append(message)

    timer = media_groups_timer.get(media_group_key)
    if timer is not None:
        timer.cancel()

    async def _delayed_process() -> None:
        await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
        await process_media_group_for_moderation(media_group_key)

    new_timer = asyncio.create_task(_delayed_process())
    media_groups_timer[media_group_key] = new_timer


def register_handlers(context) -> Router:
    global _registered_bot, _registered_router

    _configure_runtime(context)
    bot = context.predlojka_bot
    if _registered_bot is bot:
        return _registered_router

    router = Router(name="predlojka-plugin")
    router.message(lambda message: getattr(getattr(message, "from_user", None), "id", None) in pending_scheduled_publications)(handle_schedule_datetime_input)
    router.message(lambda message: getattr(getattr(message, "from_user", None), "id", None) in pending_question_answers)(handle_question_answer_input)
    router.message(lambda message: getattr(getattr(message, "from_user", None), "id", None) in pending_direct_message_answers)(handle_direct_message_answer_input)
    router.message(Command("drafts", "scheduled_posts"))(show_scheduled_posts)
    router.message(
        F.content_type.in_(["text", "sticker", "document", "audio", "voice"]),
        lambda message: not ((getattr(message, "text", None) or "").startswith("/")),
    )(accepter)
    router.message(F.content_type.in_(["photo", "video"]))(media_group_handler)

    router.callback_query(F.data == "mod_album:approve")(accept_album)
    router.callback_query(F.data == "mod_album:reject")(reject_album)
    router.callback_query(F.data == "mod_album:draft")(draft_album)
    router.callback_query(F.data == "mod_album:schedule")(schedule_album)
    router.callback_query(F.data == "mod:approve")(sender)
    router.callback_query(F.data == "mod:reject")(denier)
    router.callback_query(F.data == "mod:draft")(draft_single_post)
    router.callback_query(F.data == "mod:schedule")(schedule_single_post)
    router.callback_query(F.data == "dm:reply")(reply_in_dm)
    router.callback_query(F.data == "dm:close")(close_dm_message)
    _registered_bot = bot
    _registered_router = router
    return router


def configure(context) -> None:
    register_handlers(context)
