from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from random import choice, random

from telebot import types

from ai.ai_module import stream_ai
from analytics.stats import log_event
from config import predlojka_bot, admin, channel, channel_red, chat_mishas_den, backup_chat
from database.scheduled_posts_db import create_scheduled_post, get_due_scheduled_posts, remove_scheduled_post
from database.sqlite_db import add_to_post_counter, create_user_if_missing, user_exists
from posting.models import MediaAttachment, MediaType, Platform, Post, PostAuthor, PostOrigin
from posting.platform_ids import to_storage_user_id
from posting.runtime import post_publisher, predlojka_telegram_adapter, telegram_adapter, telegram_admin_target
from posting.services import PostFormatter, PostParser
from utils.utils import thx_for_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

q = types.ReplyKeyboardRemove()
media_groups_buffer: dict[str, list] = {}
media_groups_timer: dict[str, threading.Timer] = {}
moderation_queue: dict[int, dict] = {}
album_queue: dict[int, dict] = {}
album_media_cache: dict[int, dict] = {}
pending_question_answers: dict[int, dict] = {}
direct_message_queue: dict[int, dict] = {}
pending_direct_message_answers: dict[int, dict] = {}
pending_scheduled_publications: dict[int, dict] = {}
scheduled_publish_lock = threading.Lock()
QUESTION_ANSWER_SEPARATOR = "\n\n=====QUESTION_ANSWER_SEPARATOR=====\n\n"

MEDIA_GROUP_TIMEOUT = 2.0
BASE_DIR = Path(__file__).resolve().parent.parent
VARIBLES_DIR = BASE_DIR / "varibles"
EVENT_LIBRARY_PATH = VARIBLES_DIR / "events_library.txt"
REPORT_LIBRARY_PATH = VARIBLES_DIR / "reports_library.txt"
BLOCKED_SUBMISSION_CHATS = {channel, channel_red, chat_mishas_den}
ADVICE_MESSAGES = [
    "Совет вы можете написать в посте тег <code>#anon</code> или <code>#анон</code> - бот не будет указывать ваше имя в публикации.",
    "Подсказка: идеи для активностей можно отправлять тегом <code>#event</code> вместо обычной предложки.",
    "Подсказка: баги, опечатки и прочие технические замечания удобнее присылать через <code>#report</code>.",
    "Совет: <code>#message</code> и <code>#dm</code> отправляют сообщение админу с возможностью ответить вам в личку.",
    "Небольшой лайфхак: тег <code>#ignore</code> отправляет сообщение без ответной реакции бота.",
    "Подсказка: обычные пользовательские теги публикуются как теги поста, а служебные вроде <code>#event</code> и <code>#report</code> меняют маршрут сообщения.",
]


@dataclass
class SubmissionContent:
    clean_text: str
    public_tags: list[str]
    is_anonymous: bool
    is_question: bool
    wants_ai: bool
    ignore_reaction: bool
    route: str


def _serialize_post(post: Post) -> dict:
    return {
        "author": {
            "user_id": post.author.user_id,
            "display_name": post.author.display_name,
            "username": post.author.username,
        },
        "origin": {
            "platform": post.origin.platform.value,
            "chat_id": post.origin.chat_id,
            "user_id": post.origin.user_id,
            "message_id": post.origin.message_id,
            "media_group_id": post.origin.media_group_id,
        },
        "text": post.text,
        "public_tags": list(post.public_tags),
        "is_anonymous": post.is_anonymous,
        "is_question": post.is_question,
        "wants_ai": post.wants_ai,
        "append_author_signature": post.append_author_signature,
        "attachments": [
            {
                "media_type": attachment.media_type.value,
                "references": {platform.value: value for platform, value in attachment.references.items()},
                "file_name": attachment.file_name,
            }
            for attachment in post.attachments
        ],
    }


def _deserialize_post(data: dict) -> Post:
    return Post(
        author=PostAuthor(**data["author"]),
        origin=PostOrigin(
            platform=Platform(data["origin"]["platform"]),
            chat_id=data["origin"]["chat_id"],
            user_id=data["origin"]["user_id"],
            message_id=data["origin"].get("message_id"),
            media_group_id=data["origin"].get("media_group_id"),
        ),
        text=data.get("text", ""),
        public_tags=list(data.get("public_tags") or []),
        is_anonymous=bool(data.get("is_anonymous")),
        is_question=bool(data.get("is_question")),
        wants_ai=bool(data.get("wants_ai")),
        append_author_signature=bool(data.get("append_author_signature", True)),
        attachments=[
            MediaAttachment(
                media_type=MediaType(item["media_type"]),
                references={Platform(key): value for key, value in (item.get("references") or {}).items()},
                file_name=item.get("file_name"),
            )
            for item in data.get("attachments") or []
        ],
    )


def _build_platform_post_from_message(message, content: SubmissionContent) -> Post:
    post = telegram_adapter.create_post_from_message(message)
    post.text = content.clean_text
    post.public_tags = list(content.public_tags)
    post.is_anonymous = content.is_anonymous
    post.is_question = content.is_question
    post.wants_ai = content.wants_ai
    return post


def _build_platform_post_from_album(items: list, content: SubmissionContent) -> Post:
    post = telegram_adapter.create_post_from_media_group(items)
    post.text = content.clean_text
    post.public_tags = list(content.public_tags)
    post.is_anonymous = content.is_anonymous
    post.is_question = content.is_question
    post.wants_ai = content.wants_ai
    return post


def safe_delete_message(chat_id: int, message_id: int, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            predlojka_telegram_adapter.delete_message(chat_id, message_id)
            return True
        except Exception as error:
            logger.error(f"Ошибка при удалении сообщения {message_id} (попытка {attempt + 1}): {error}")
            time.sleep(0.4)
    return False


def safe_send_media_group(chat_id: int, media: list, max_retries: int = 3) -> list | None:
    for attempt in range(max_retries):
        try:
            return predlojka_telegram_adapter.send_media_group(chat_id, media)
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


def _can_submit_service_message(chat_id: int) -> bool:
    return chat_id not in {channel, channel_red}


def _parse_submission_text(text: str | None) -> SubmissionContent:
    parsed = PostParser.parse_submission_text(text)
    return SubmissionContent(
        clean_text=parsed.clean_text,
        public_tags=list(parsed.public_tags),
        is_anonymous=parsed.is_anonymous,
        is_question=parsed.is_question,
        wants_ai=parsed.wants_ai,
        ignore_reaction=parsed.ignore_reaction,
        route=parsed.route,
    )


def _compose_publish_text(content: SubmissionContent, user_name: str) -> str:
    parts: list[str] = []
    if content.clean_text:
        parts.append(content.clean_text)
    if content.public_tags:
        parts.append("🏷️ " + " ".join(content.public_tags))
    parts.append("🤫 Аноним" if content.is_anonymous else f"👤 {user_name}")
    return "\n\n".join(parts).strip()


def _build_service_text(content: SubmissionContent, user_name: str) -> str:
    parts: list[str] = []
    if content.clean_text:
        parts.append(content.clean_text)
    if content.public_tags:
        parts.append("🏷️ " + " ".join(content.public_tags))
    parts.append("🤫 Аноним" if content.is_anonymous else f"👤 {user_name}")
    return "\n\n".join(parts).strip()


def _maybe_send_advice(message, content: SubmissionContent) -> None:
    if content.ignore_reaction:
        return
    if random() >= 0.4:
        return
    predlojka_telegram_adapter.send_message(
        message.chat.id,
        choice(ADVICE_MESSAGES),
        reply_to_message_id=message.message_id,
        parse_mode="HTML",
    )


def _acknowledge_submission(message, content: SubmissionContent, user_name: str) -> None:
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

    predlojka_telegram_adapter.send_message(message.chat.id, text, reply_markup=q)
    _maybe_send_advice(message, content)


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


def _send_report_library_snapshot() -> None:
    if not REPORT_LIBRARY_PATH.exists():
        return

    try:
        with REPORT_LIBRARY_PATH.open("rb") as file:
            predlojka_telegram_adapter.send_document(
                backup_chat,
                file,
                visible_file_name="reports_library.txt",
                caption="Новый репорт добавлен в reports_library.txt",
                disable_notification=True,
            )
    except Exception as error:
        logger.error(f"Не удалось отправить reports_library.txt в debug chat: {error}")


def _copy_single_message_to_admin(message):
    try:
        return predlojka_telegram_adapter.copy_message(admin, message.chat.id, message.message_id)
    except Exception as error:
        logger.error(f"Не удалось скопировать сообщение админу: {error}")
        return None


def _store_special_route(message, content: SubmissionContent) -> None:
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
        _send_report_library_snapshot()

    copied_message = _copy_single_message_to_admin(message)
    summary = _build_route_summary(message, content, user_name, route_label=route_label, content_type=message.content_type)

    if content.route == "message":
        control_message = predlojka_telegram_adapter.send_message(
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
        predlojka_telegram_adapter.send_message(
            admin,
            summary,
            reply_to_message_id=copied_message.message_id if copied_message else None,
        )

    _acknowledge_submission(message, content, user_name)
    log_event(
        f"{content.route}_submitted",
        bot="predlojka",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"content_type": message.content_type, "anonymous": content.is_anonymous, "tags": content.public_tags},
    )


def _store_special_route_album(items: list, content: SubmissionContent) -> None:
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
        _send_report_library_snapshot()

    if media:
        sent_preview = safe_send_media_group(admin, media)
        if sent_preview:
            preview_ids = [item.message_id for item in sent_preview]

    summary = _build_route_summary(first_item, content, user_name, route_label=route_label, content_type="album", items_count=len(media))
    if content.route == "message":
        control_message = predlojka_telegram_adapter.send_message(
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
        predlojka_telegram_adapter.send_message(admin, summary, reply_to_message_id=preview_ids[0] if preview_ids else None)

    _acknowledge_submission(first_item, content, user_name)
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


def _send_admin_preview(message, content: SubmissionContent, publish_text: str) -> None:
    markup = _build_moderation_markup(is_question=content.is_question)
    preview_caption = publish_text or _compose_publish_text(content, _display_name(message.from_user))
    platform_post = _build_platform_post_from_message(message, content)
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
        admin_message = predlojka_telegram_adapter.send_message(
            admin,
            f"{_preview_title(content, message.content_type)}\n\n{preview_caption}",
            reply_markup=markup,
        )
    elif message.content_type == "sticker":
        payload["file_id"] = message.sticker.file_id
        admin_message = predlojka_telegram_adapter.send_sticker(admin, message.sticker.file_id, reply_markup=markup)
        helper = predlojka_telegram_adapter.send_message(admin, preview_caption, reply_to_message_id=admin_message.message_id)
        payload["helper_message_id"] = helper.message_id
    elif message.content_type == "photo":
        payload["file_id"] = message.photo[-1].file_id
        admin_message = predlojka_telegram_adapter.send_photo(admin, message.photo[-1].file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "video":
        payload["file_id"] = message.video.file_id
        admin_message = predlojka_telegram_adapter.send_video(admin, message.video.file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "document":
        payload["file_id"] = message.document.file_id
        admin_message = predlojka_telegram_adapter.send_document(admin, message.document.file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "audio":
        payload["file_id"] = message.audio.file_id
        admin_message = predlojka_telegram_adapter.send_audio(admin, message.audio.file_id, caption=preview_caption, reply_markup=markup)
    elif message.content_type == "voice":
        payload["file_id"] = message.voice.file_id
        admin_message = predlojka_telegram_adapter.send_voice(admin, message.voice.file_id, caption=preview_caption, reply_markup=markup)
    else:
        raise ValueError(f"Неподдерживаемый тип контента: {message.content_type}")

    moderation_queue[admin_message.message_id] = payload


def _send_external_admin_preview(post: Post) -> None:
    preview_text = PostFormatter.compose_publish_text(post)
    preview_result = telegram_adapter.publish_post(telegram_admin_target, post, preview_text)
    control_message = telegram_adapter.send_text(
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
        "source_user_id": to_storage_user_id(post.origin.platform, post.origin.user_id),
        "question_text": post.text,
        "public_tags": list(post.public_tags),
        "is_anonymous": post.is_anonymous,
        "author_name": post.author.display_name,
        "post_data": _serialize_post(post),
    }


def _notify_publish_warnings(errors: dict) -> None:
    if not errors:
        return
    warning_text = "Часть площадок не приняла публикацию:\n" + "\n".join(f"- {error}" for error in errors.values())
    predlojka_telegram_adapter.send_message(admin, warning_text)


def _publish_payload(payload: dict) -> None:
    content_type = payload["content_type"]
    publish_text = payload["publish_text"]
    file_id = payload.get("file_id")
    parse_mode = payload.get("parse_mode")
    post_data = payload.get("post_data")

    if post_data:
        outcome = post_publisher.publish_post(
            _deserialize_post(post_data),
            rendered_text=publish_text,
            disable_notification=True,
            parse_mode=parse_mode,
        )
        if outcome.has_errors:
            _notify_publish_warnings(outcome.errors)
        return

    if content_type == "text":
        predlojka_telegram_adapter.send_message(channel, publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "sticker":
        predlojka_telegram_adapter.send_sticker(channel, file_id, disable_notification=True)
        if publish_text:
            predlojka_telegram_adapter.send_message(channel, publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "photo":
        predlojka_telegram_adapter.send_photo(channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "video":
        predlojka_telegram_adapter.send_video(channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "document":
        predlojka_telegram_adapter.send_document(channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "audio":
        predlojka_telegram_adapter.send_audio(channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
        return
    if content_type == "voice":
        predlojka_telegram_adapter.send_voice(channel, file_id, caption=publish_text, disable_notification=True, parse_mode=parse_mode)
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


def _publish_album_payload(payload: dict) -> None:
    post_data = payload.get("post_data")
    if post_data:
        outcome = post_publisher.publish_post(
            _deserialize_post(post_data),
            rendered_text=payload.get("publish_text", ""),
            disable_notification=True,
            parse_mode=payload.get("parse_mode"),
        )
        if outcome.has_errors:
            _notify_publish_warnings(outcome.errors)
        return
    media = _deserialize_album_media(payload["media"])
    sent = safe_send_media_group(channel, media)
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


def _publish_question_with_answer(payload: dict, answer_text: str) -> None:
    _publish_payload(_build_ready_question_payload(payload, answer_text))


def _clear_preview_messages(payload: dict, moderation_message_id: int | None = None) -> None:
    helper_message_id = payload.get("helper_message_id")
    if helper_message_id:
        safe_delete_message(admin, helper_message_id)
    for preview_message_id in payload.get("preview_message_ids", []):
        safe_delete_message(admin, preview_message_id)
    if moderation_message_id is not None:
        safe_delete_message(admin, moderation_message_id)


def _clear_album_preview(queue_payload: dict, moderation_message_id: int | None = None) -> None:
    for preview_id in queue_payload.get("preview_ids", []):
        safe_delete_message(admin, preview_id)
    if moderation_message_id is not None:
        safe_delete_message(admin, moderation_message_id)


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


def _request_schedule_datetime(admin_user_id: int, pending_payload: dict, *, reply_to_message_id: int | None = None, callback_query_id: str | None = None) -> None:
    pending_scheduled_publications[admin_user_id] = pending_payload
    prompt = predlojka_telegram_adapter.send_message(
        admin,
        "Напиши дату и время публикации.\n\nПоддерживаю форматы: ДД.ММ.ГГГГ ЧЧ:ММ, ДД.ММ ЧЧ:ММ или ГГГГ-ММ-ДД ЧЧ:ММ.\nДля отмены отправь /cancel_schedule",
        reply_to_message_id=reply_to_message_id,
    )
    predlojka_telegram_adapter.register_next_step_handler(prompt, handle_schedule_datetime_input)
    if callback_query_id is not None:
        predlojka_telegram_adapter.answer_callback_query(callback_query_id, "Жду дату и время публикации.")


def _save_single_payload_as_draft(payload: dict, moderation_message_id: int, admin_user_id: int, chat_id: int) -> None:
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
    _clear_preview_messages(payload, moderation_message_id)
    predlojka_telegram_adapter.send_message(admin, f"Черновик сохранён. ID задачи: {record_id}")
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


def _save_album_payload_as_draft(queue_payload: dict, storage_payload: dict, moderation_message_id: int, admin_user_id: int, chat_id: int) -> None:
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
    _clear_album_preview(queue_payload, moderation_message_id)
    predlojka_telegram_adapter.send_message(admin, f"Черновик альбома сохранён. ID задачи: {record_id}")
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


def handle_schedule_datetime_input(message):
    pending = pending_scheduled_publications.get(message.from_user.id)
    if pending is None:
        predlojka_telegram_adapter.reply_to(message, "Не вижу публикации, которая ждёт планирования.")
        return

    if message.text and message.text.strip() == "/cancel_schedule":
        _restore_scheduled_pending(pending)
        pending_scheduled_publications.pop(message.from_user.id, None)
        predlojka_telegram_adapter.reply_to(message, "Отменяю планирование и возвращаю запись в очередь модерации.")
        return

    publish_at = _parse_schedule_datetime(message.text or "")
    if publish_at is None:
        retry_prompt = predlojka_telegram_adapter.reply_to(
            message,
            "Не смогла распознать дату. Попробуй формат вроде 05.04.2026 14:30.",
        )
        predlojka_telegram_adapter.register_next_step_handler(retry_prompt, handle_schedule_datetime_input)
        return

    if publish_at <= datetime.now():
        retry_prompt = predlojka_telegram_adapter.reply_to(
            message,
            "Нужно указать время в будущем. Попробуй ещё раз.",
        )
        predlojka_telegram_adapter.register_next_step_handler(retry_prompt, handle_schedule_datetime_input)
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
            _clear_album_preview(pending["queue_payload"], pending["moderation_message_id"])
        else:
            _clear_preview_messages(pending["storage_payload"], pending["moderation_message_id"])
        safe_delete_message(admin, message.message_id)
        pending_scheduled_publications.pop(message.from_user.id, None)
        predlojka_telegram_adapter.send_message(
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
        predlojka_telegram_adapter.reply_to(message, "Не получилось сохранить публикацию. Вернула её в очередь модерации.")


def _request_question_answer(call, payload: dict) -> None:
    pending_question_answers[call.from_user.id] = {
        "payload": payload,
        "moderation_message_id": call.message.message_id,
        "action": "publish",
    }
    prompt = predlojka_telegram_adapter.send_message(
        admin,
        "Отлично! Я рада, что ты заинтересовался) Напиши ответ текстиком, а я передам в канал! (^-^)\n\nЕсли всё же передумал, напиши /cancel_question_answer",
        reply_to_message_id=call.message.message_id,
    )
    predlojka_telegram_adapter.register_next_step_handler(prompt, handle_question_answer_input)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Жду текст ответа.")
    log_event(
        "question_answer_requested",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )


def _request_question_answer_for_action(call, payload: dict, action: str) -> None:
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
    prompt = predlojka_telegram_adapter.send_message(
        admin,
        f"Напиши ответ текстом, и я {action_text} вопрос одним готовым постом.\n\nЕсли передумал, напиши /cancel_question_answer",
        reply_to_message_id=call.message.message_id,
    )
    predlojka_telegram_adapter.register_next_step_handler(prompt, handle_question_answer_input)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Жду текст ответа.")


def handle_question_answer_input(message):
    pending = pending_question_answers.get(message.from_user.id)
    if pending is None:
        predlojka_telegram_adapter.reply_to(message, "Не могу найти вопроса, который ожидает ответа... (⊙▂⊙)")
        return

    if message.text and message.text.strip() == "/cancel_question_answer":
        payload = pending["payload"]
        moderation_queue[pending["moderation_message_id"]] = payload
        pending_question_answers.pop(message.from_user.id, None)
        predlojka_telegram_adapter.reply_to(message, "Как скажешь, нет так нет! Вернула воспрос в очередь на модерацию.")
        return

    answer_text = (message.text or "").strip()
    if not answer_text:
        retry_prompt = predlojka_telegram_adapter.reply_to(
            message,
            "Боюсь, я смогу принять только текст в качестве ответа... Увы (︶︹︶)",
        )
        predlojka_telegram_adapter.register_next_step_handler(retry_prompt, handle_question_answer_input)
        return

    payload = pending["payload"]
    moderation_message_id = pending["moderation_message_id"]
    action = pending.get("action", "publish")
    ready_payload = _build_ready_question_payload(payload, answer_text)

    try:
        if action == "publish":
            _publish_payload(ready_payload)
            _clear_preview_messages(ready_payload, moderation_message_id)
            safe_delete_message(admin, message.message_id)
            pending_question_answers.pop(message.from_user.id, None)
            predlojka_telegram_adapter.send_message(admin, "Вопрос с вашим прелестным ответом опубликован в канале! (｡•̀ᴗ-)✧")
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
            _save_single_payload_as_draft(ready_payload, moderation_message_id, message.from_user.id, message.chat.id)
            safe_delete_message(admin, message.message_id)
            pending_question_answers.pop(message.from_user.id, None)
            return

        if action == "schedule":
            pending_question_answers.pop(message.from_user.id, None)
            safe_delete_message(admin, message.message_id)
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
            _request_schedule_datetime(
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
        predlojka_telegram_adapter.reply_to(message, "Не получилось обработать вопрос с ответом. Вернула его в очередь модерации!")


def _request_direct_message_answer(call, payload: dict) -> None:
    pending_direct_message_answers[call.from_user.id] = {
        "payload": payload,
        "control_message_id": call.message.message_id,
    }
    prompt = predlojka_telegram_adapter.send_message(
        admin,
        "Напиши текст ответа, и я отправлю его пользователю в ЛС.\n\nЕсли передумал, напиши /cancel_dm_answer",
        reply_to_message_id=call.message.message_id,
    )
    predlojka_telegram_adapter.register_next_step_handler(prompt, handle_direct_message_answer_input)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Жду ответ для отправки в ЛС.")


def handle_direct_message_answer_input(message):
    pending = pending_direct_message_answers.get(message.from_user.id)
    if pending is None:
        predlojka_telegram_adapter.reply_to(message, "Не вижу сообщения, которое ждёт ответа.")
        return

    if message.text and message.text.strip() == "/cancel_dm_answer":
        direct_message_queue[pending["control_message_id"]] = pending["payload"]
        pending_direct_message_answers.pop(message.from_user.id, None)
        predlojka_telegram_adapter.reply_to(message, "Хорошо, отменяю ответ и возвращаю сообщение в очередь.")
        return

    answer_text = (message.text or "").strip()
    if not answer_text:
        retry_prompt = predlojka_telegram_adapter.reply_to(message, "Смогу переслать пользователю только текстовый ответ.")
        predlojka_telegram_adapter.register_next_step_handler(retry_prompt, handle_direct_message_answer_input)
        return

    payload = pending["payload"]
    control_message_id = pending["control_message_id"]

    try:
        predlojka_telegram_adapter.send_message(
            payload["source_user_id"],
            "Ответ администрации:\n\n" + answer_text,
        )
        pending_direct_message_answers.pop(message.from_user.id, None)
        safe_delete_message(admin, control_message_id)
        safe_delete_message(admin, message.message_id)
        predlojka_telegram_adapter.send_message(admin, "Ответ пользователю отправлен в ЛС.")
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
        predlojka_telegram_adapter.reply_to(message, "Не получилось отправить ответ в ЛС. Вернула сообщение в очередь.")


def _handle_ai_request(message, content: SubmissionContent) -> None:
    name = _display_name(message.from_user)
    prompt_text = content.clean_text or message.text
    response_message = None if content.ignore_reaction else predlojka_telegram_adapter.reply_to(message, "Думаю... (*￣3￣)╭")
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
        if response_message is not None:
            predlojka_telegram_adapter.edit_message_text(full_text, chat_id=message.chat.id, message_id=response_message.message_id)
        elif not content.ignore_reaction:
            predlojka_telegram_adapter.send_message(message.chat.id, full_text)
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
            if response_message is not None:
                predlojka_telegram_adapter.edit_message_text(
                    "Извините, что-то пошло не так... Попробуй ещё раз позже (^_^;)",
                    chat_id=message.chat.id,
                    message_id=response_message.message_id,
                )
            elif not content.ignore_reaction:
                predlojka_telegram_adapter.send_message(message.chat.id, "Извините, что-то пошло не так... Попробуй ещё раз позже (^_^;)")
        except Exception:
            if not content.ignore_reaction:
                predlojka_telegram_adapter.send_message(message.chat.id, "Извините, ошибка обработки...")
    finally:
        if loop is not None:
            loop.close()


def _submit_single_message(message) -> None:
    content_text = message.text if message.content_type == "text" else message.caption
    content = _parse_submission_text(content_text)

    if content.ignore_reaction:
        return

    if content.route == "post" and message.content_type == "text" and content.wants_ai and _can_use_ai(message.chat.id):
        _handle_ai_request(message, content)
        return

    if content.route == "post" and not _can_submit_post(message.chat.id):
        return

    if content.route != "post" and not _can_submit_service_message(message.chat.id):
        return

    user_name = _display_name(message.from_user)

    if content.route != "post":
        _store_special_route(message, content)
        return

    publish_text = _compose_publish_text(content, user_name)
    add_to_post_counter(message.from_user.id)
    _acknowledge_submission(message, content, user_name)
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
        predlojka_telegram_adapter.reply_to(message, "Боюсь, такой команды я не знаю... (｡•́︿•̀｡)")
        return

    _submit_single_message(message)


def _build_album_media(items: list, publish_caption: str) -> list:
    return _deserialize_album_media(_serialize_album_media(items, publish_caption))


def process_media_group_for_moderation(media_group_id: str) -> None:
    try:
        items = media_groups_buffer.pop(media_group_id, [])
        media_groups_timer.pop(media_group_id, None)
        if not items:
            return

        user = items[0].from_user
        captions = [item.caption for item in items if item.caption]
        content = _parse_submission_text("\n".join(captions))
        if content.ignore_reaction:
            return
        if content.route == "post" and not _can_submit_post(items[0].chat.id):
            return
        if content.route != "post" and not _can_submit_service_message(items[0].chat.id):
            return

        if content.route != "post":
            _store_special_route_album(items, content)
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
        _acknowledge_submission(items[0], content, user_name)

        sent_preview = safe_send_media_group(admin, media)
        if not sent_preview:
            logger.error("Не удалось отправить альбом админу")
            return

        control_message = predlojka_telegram_adapter.send_message(
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


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod_album:approve")
def accept_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    media_payload = album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None or media_payload is None:
        if queue_payload is not None:
            album_queue[call.message.message_id] = queue_payload
        if media_payload is not None:
            album_media_cache[call.message.message_id] = media_payload
        r = "Этот альбом уже обработан или устарел."
        predlojka_telegram_adapter.answer_callback_query(call.id, r)
        return

    try:
        _publish_album_payload(media_payload)
    except Exception as error:
        album_queue[call.message.message_id] = queue_payload
        album_media_cache[call.message.message_id] = media_payload
        logger.error(f"Ошибка при публикации альбома: {error}")
        predlojka_telegram_adapter.answer_callback_query(call.id, "Не получилось опубликовать альбом.")
        return

    _clear_album_preview(queue_payload, call.message.message_id)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Альбом опубликован!")
    log_event(
        "album_approved",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": queue_payload["source_user_id"], "is_question": queue_payload["is_question"]},
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod_album:reject")
def reject_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Боюсь, этот альбом уже обработан или устарел... ")
        return

    _clear_album_preview(queue_payload, call.message.message_id)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Альбом отклонён! (￣^￣)ゞ")
    log_event(
        "album_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": queue_payload["source_user_id"], "is_question": queue_payload["is_question"]},
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod_album:draft")
def draft_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    storage_payload = album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None or storage_payload is None:
        if queue_payload is not None:
            album_queue[call.message.message_id] = queue_payload
        if storage_payload is not None:
            album_media_cache[call.message.message_id] = storage_payload
        predlojka_telegram_adapter.answer_callback_query(call.id, "Этот альбом уже обработан или устарел.")
        return

    _save_album_payload_as_draft(queue_payload, storage_payload, call.message.message_id, call.from_user.id, call.message.chat.id)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Альбом сохранён в черновиках.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod_album:schedule")
def schedule_album(call):
    queue_payload = album_queue.pop(call.message.message_id, None)
    media_payload = album_media_cache.pop(call.message.message_id, None)
    if queue_payload is None or media_payload is None:
        if queue_payload is not None:
            album_queue[call.message.message_id] = queue_payload
        if media_payload is not None:
            album_media_cache[call.message.message_id] = media_payload
        predlojka_telegram_adapter.answer_callback_query(call.id, "Этот альбом уже обработан или устарел.")
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
    _request_schedule_datetime(
        call.from_user.id,
        pending_payload,
        reply_to_message_id=call.message.message_id,
        callback_query_id=call.id,
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:approve")
def sender(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Эта запись уже обработана или устарела... (◔~◔)")
        return

    if payload["is_question"] and not payload.get("question_answer_bundle"):
        _request_question_answer(call, payload)
        return

    try:
        _publish_payload(payload)
        _clear_preview_messages(payload, call.message.message_id)
        predlojka_telegram_adapter.answer_callback_query(call.id, "Сообщение опубликовано")
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
        predlojka_telegram_adapter.answer_callback_query(call.id, "Ошибка при публикации")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:reject")
def denier(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Эта запись уже обработана или устарела.")
        return

    _clear_preview_messages(payload, call.message.message_id)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Сообщение отклонено")
    log_event(
        "question_rejected" if payload["is_question"] else "post_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )
    logger.info("Пост отклонён")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:draft")
def draft_single_post(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Эта запись уже обработана или устарела.")
        return

    if payload["is_question"] and not payload.get("question_answer_bundle"):
        _request_question_answer_for_action(call, payload, "draft")
        return

    _save_single_payload_as_draft(payload, call.message.message_id, call.from_user.id, call.message.chat.id)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Запись сохранена в черновиках.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:schedule")
def schedule_single_post(call):
    payload = moderation_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Эта запись уже обработана или устарела.")
        return

    if payload["is_question"] and not payload.get("question_answer_bundle"):
        _request_question_answer_for_action(call, payload, "schedule")
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
    _request_schedule_datetime(
        call.from_user.id,
        pending_payload,
        reply_to_message_id=call.message.message_id,
        callback_query_id=call.id,
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "dm:reply")
def reply_in_dm(call):
    payload = direct_message_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Это сообщение уже обработано или устарело.")
        return
    _request_direct_message_answer(call, payload)


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "dm:close")
def close_dm_message(call):
    payload = direct_message_queue.pop(call.message.message_id, None)
    if payload is None:
        predlojka_telegram_adapter.answer_callback_query(call.id, "Это сообщение уже закрыто или устарело.")
        return
    safe_delete_message(admin, call.message.message_id)
    predlojka_telegram_adapter.answer_callback_query(call.id, "Сообщение закрыто.")
    log_event(
        "direct_message_closed",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"source_user_id": payload["source_user_id"], "content_type": payload["content_type"]},
    )


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("+album|"))
def accept_album_legacy(call):
    predlojka_telegram_adapter.answer_callback_query(call.id, "Старая кнопка модерации больше не поддерживается. Перепроверь альбом заново.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("-album|"))
def reject_album_legacy(call):
    predlojka_telegram_adapter.answer_callback_query(call.id, "Старая кнопка модерации больше не поддерживается.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("+") and not call.data.startswith("+album|"))
def sender_legacy(call):
    predlojka_telegram_adapter.answer_callback_query(call.id, "Эта старая кнопка публикации уже неактивна.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data.startswith("&"))
def st_sender_legacy(call):
    predlojka_telegram_adapter.answer_callback_query(call.id, "Эта старая кнопка публикации уже неактивна.")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "-")
def denier_legacy(call):
    predlojka_telegram_adapter.answer_callback_query(call.id, "Эта старая кнопка модерации уже неактивна.")


def publish_due_scheduled_posts() -> None:
    if not scheduled_publish_lock.acquire(blocking=False):
        return

    try:
        due_posts = get_due_scheduled_posts()
        for record in due_posts:
            try:
                if record["content_type"] == "album":
                    _publish_album_payload(record["payload"])
                else:
                    _publish_payload(record["payload"])
                remove_scheduled_post(record["doc_id"])
                log_event(
                    "scheduled_post_published",
                    bot="predlojka",
                    metadata={
                        "schedule_id": record["doc_id"],
                        "content_type": record["content_type"],
                        "source_user_id": record["source_user_id"],
                    },
                )
            except Exception as error:
                logger.error(f"Не удалось опубликовать отложенную запись {record['doc_id']}: {error}")
    finally:
        scheduled_publish_lock.release()


def _ensure_user_for_post(post: Post, *, first_name: str | None = None, last_name: str | None = None) -> int:
    storage_user_id = to_storage_user_id(post.origin.platform, post.origin.user_id)
    if not user_exists(storage_user_id):
        create_user_if_missing(storage_user_id, first_name or post.author.display_name, last_name)
    return storage_user_id


def submit_external_post(post: Post, *, acknowledge_callback=None) -> None:
    _ensure_user_for_post(post)
    storage_user_id = to_storage_user_id(post.origin.platform, post.origin.user_id)
    add_to_post_counter(storage_user_id)

    if acknowledge_callback is not None:
        acknowledge_callback(post)

    _send_external_admin_preview(post)
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
