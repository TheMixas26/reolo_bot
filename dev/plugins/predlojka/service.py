from __future__ import annotations

import logging, random, datetime, time
from dataclasses import dataclass

from database.sqlite_db import create_user_if_missing, user_exists
from posting.models import MediaAttachment, MediaType, Platform, Post, PostAuthor, PostOrigin
from posting.platform_ids import to_storage_user_id
from posting.services import PostParser
from varibles.dialogue_loader import TEXT


logger = logging.getLogger(__name__)

predlojka_telegram_adapter = None
telegram_adapter = None
channel = None
channel_red = None
chat_mishas_den = None
BLOCKED_SUBMISSION_CHATS: set[int | str | None] = set()


@dataclass
class SubmissionContent:
    clean_text: str
    public_tags: list[str]
    is_anonymous: bool
    is_question: bool
    wants_ai: bool
    ignore_reaction: bool
    route: str


def configure(context) -> None:
    global predlojka_telegram_adapter, telegram_adapter, channel, channel_red, chat_mishas_den, BLOCKED_SUBMISSION_CHATS

    predlojka_telegram_adapter = context.tg_adapter
    telegram_adapter = context.tg_adapter
    channel = context.config.channel
    channel_red = context.config.channel_red
    chat_mishas_den = context.config.chat_mishas_den
    BLOCKED_SUBMISSION_CHATS = {channel, channel_red, chat_mishas_den}


def ensure_user_exists(user) -> None:
    if not user_exists(user.id):
        create_user_if_missing(user.id, user.first_name, user.last_name)


def storage_user_id_for_post(post: Post) -> int:
    return to_storage_user_id(post.origin.platform, post.origin.user_id)


def ensure_post_author_exists(post: Post, *, first_name: str | None = None, last_name: str | None = None) -> int:
    storage_user_id = storage_user_id_for_post(post)
    if not user_exists(storage_user_id):
        create_user_if_missing(storage_user_id, first_name or post.author.display_name, last_name)
    return storage_user_id


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
        "formatted_text": post.formatted_text,
        "text_parse_mode": post.text_parse_mode,
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
        formatted_text=data.get("formatted_text"),
        text_parse_mode=data.get("text_parse_mode"),
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
    if post.formatted_text:
        post.formatted_text = telegram_adapter._strip_submission_tags_from_formatted_text(post.formatted_text)
    post.public_tags = list(content.public_tags)
    post.is_anonymous = content.is_anonymous
    post.is_question = content.is_question
    post.wants_ai = content.wants_ai
    return post


def _build_platform_post_from_album(items: list, content: SubmissionContent) -> Post:
    post = telegram_adapter.create_post_from_media_group(items)
    post.text = content.clean_text
    if post.formatted_text:
        post.formatted_text = telegram_adapter._strip_submission_tags_from_formatted_text(post.formatted_text)
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

def _preview_scheduled_payload(payload: dict, content_type: str) -> str:
    if content_type == "album":
        media = payload.get("media") or []
        first_caption = ""
        if media:
            first_caption = (media[0].get("caption") or "").strip()
        snippet = first_caption or f"Альбом из {len(media)} элементов"
    else:
        snippet = (payload.get("publish_text") or "").strip()

    snippet = snippet.replace("\n", " ")
    if len(snippet) > 90:
        snippet = snippet[:87] + "..."
    return snippet or "(без текста)"


def thx_for_message(user_name: str, mes_type: str) -> str:
    FUN = random.random()

    time = "day" if 6 <= datetime.now().hour < 23 else "night"

    if mes_type == '!':
        if FUN < 0.9:
            return TEXT("thx", time, "variants_v", name=user_name)
        elif FUN >= 0.98:
            return TEXT("thx", time, "podval_variants_v", name=user_name)
        else:
            return TEXT("thx", time, "secret_variants_v", name=user_name)

    elif mes_type == '?':
        return TEXT("thx", time, "variants_q", name=user_name)

    elif mes_type == 'event':
        return TEXT("thx", time, "events_variants")

    elif mes_type == 'report':
        return TEXT("thx", time, "report_variants")

    elif mes_type == 'message':
        return TEXT("thx", time, "message_variants")

    else:
        return TEXT("thx", time, "variants_v", name=user_name)