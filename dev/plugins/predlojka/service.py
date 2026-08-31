from __future__ import annotations

import asyncio
import inspect
import logging, random
from dataclasses import dataclass
from datetime import datetime

from database.sqlite_db import create_user_if_missing, user_exists
from .classes import MediaAttachment, MediaType, Platform, Post, PostAuthor, PostOrigin, PostFactory, PostFormatter
from aiogram import types
from .classes import to_storage_user_id, PostParser
from varibles import TEXT
from html import escape

logger = logging.getLogger(__name__)


def apply_html_entities(text, entities=None, custom_subs=None):
    return escape(text or "")

predlojka_bot = None
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
    global predlojka_bot, channel, channel_red, chat_mishas_den, BLOCKED_SUBMISSION_CHATS

    predlojka_bot = context.predlojka_bot
    channel = context.config.channel
    channel_red = context.config.channel_red
    chat_mishas_den = context.config.chat_mishas_den
    BLOCKED_SUBMISSION_CHATS = {channel, channel_red, chat_mishas_den}


async def ensure_user_exists(user) -> None:
    if not await user_exists(user.id):
        await create_user_if_missing(user.id, user.first_name, user.last_name)


def storage_user_id_for_post(post: Post) -> int:
    return to_storage_user_id(post.origin.platform, post.origin.user_id)


async def ensure_post_author_exists(post: Post, *, first_name: str | None = None, last_name: str | None = None) -> int:
    storage_user_id = storage_user_id_for_post(post)
    if not await user_exists(storage_user_id):
        await create_user_if_missing(storage_user_id, first_name or post.author.display_name, last_name)
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


def create_post_from_message(message, *, append_author_signature: bool = True) -> Post:
        attachments: list[MediaAttachment] = []
        content_type = getattr(message, "content_type", "text")

        if content_type == "sticker":
            attachments.append(MediaAttachment(media_type=MediaType.STICKER, references={Platform.TELEGRAM: message.sticker.file_id}))
        elif content_type == "photo":
            attachments.append(MediaAttachment(media_type=MediaType.PHOTO, references={Platform.TELEGRAM: message.photo[-1].file_id}))
        elif content_type == "video":
            attachments.append(MediaAttachment(media_type=MediaType.VIDEO, references={Platform.TELEGRAM: message.video.file_id}))
        elif content_type == "document":
            attachments.append(
                MediaAttachment(
                    media_type=MediaType.DOCUMENT,
                    references={Platform.TELEGRAM: message.document.file_id},
                    file_name=getattr(message.document, "file_name", None),
                )
            )
        elif content_type == "audio":
            attachments.append(
                MediaAttachment(
                    media_type=MediaType.AUDIO,
                    references={Platform.TELEGRAM: message.audio.file_id},
                    file_name=getattr(message.audio, "file_name", None),
                )
            )
        elif content_type == "voice":
            attachments.append(MediaAttachment(media_type=MediaType.VOICE, references={Platform.TELEGRAM: message.voice.file_id}))

        raw_text, entities = _resolve_text_payload(message)
        formatted_text, text_parse_mode = _build_formatted_text(raw_text, entities)
        author = PostAuthor(
            user_id=message.from_user.id,
            display_name=build_display_name(message.from_user),
            username=getattr(message.from_user, "username", None),
        )
        origin = PostOrigin(
            platform=Platform.TELEGRAM,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            message_id=message.message_id,
            media_group_id=getattr(message, "media_group_id", None),
        )
        post = PostFactory.create_submission_post(
            author=author,
            origin=origin,
            raw_text=raw_text,
            attachments=attachments,
            append_author_signature=append_author_signature,
        )
        post.formatted_text = formatted_text
        post.text_parse_mode = text_parse_mode
        return post

def create_post_from_media_group(self, messages: list) -> Post:
        if not messages:
            raise ValueError("Пустая медиагруппа")

        attachments: list[MediaAttachment] = []
        for message in messages:
            if message.content_type == "photo":
                attachments.append(MediaAttachment(media_type=MediaType.PHOTO, references={Platform.TELEGRAM: message.photo[-1].file_id}))
            elif message.content_type == "video":
                attachments.append(MediaAttachment(media_type=MediaType.VIDEO, references={Platform.TELEGRAM: message.video.file_id}))

        first_message = messages[0]
        raw_text = "\n".join(item.caption for item in messages if item.caption)
        formatted_source, _ = self._resolve_album_text_payload(messages)
        formatted_text = self._strip_submission_tags_from_formatted_text(formatted_source) if formatted_source else None
        text_parse_mode = "HTML" if formatted_text else None
        author = PostAuthor(
            user_id=first_message.from_user.id,
            display_name=self.build_display_name(first_message.from_user),
            username=getattr(first_message.from_user, "username", None),
        )
        origin = PostOrigin(
            platform=Platform.TELEGRAM,
            chat_id=first_message.chat.id,
            user_id=first_message.from_user.id,
            message_id=first_message.message_id,
            media_group_id=str(first_message.media_group_id),
        )
        post = PostFactory.create_submission_post(author=author, origin=origin, raw_text=raw_text, attachments=attachments)
        post.formatted_text = formatted_text
        post.text_parse_mode = text_parse_mode
        return post    



def _build_formatted_text(text: str | None, entities: list | None) -> tuple[str | None, str | None]:
        if not text:
            return None, None
        formatted = apply_html_entities(text, entities, None)
        cleaned = _strip_submission_tags_from_formatted_text(formatted)
        if not cleaned:
            return None, None
        return cleaned, "HTML"


def _resolve_text_payload(message) -> tuple[str | None, list | None]:
    content_type = getattr(message, "content_type", "text")
    if content_type == "text":
        return message.text, getattr(message, "entities", None)
    return message.caption, getattr(message, "caption_entities", None)


def _resolve_album_text_payload(messages: list) -> tuple[str | None, list | None]:
    formatted_chunks: list[str] = []
    for message in messages:
        caption = getattr(message, "caption", None)
        if not caption:
            continue
        formatted_chunks.append(
            apply_html_entities(caption, getattr(message, "caption_entities", None), None)
        )
    if not formatted_chunks:
        return None, None
    return "\n".join(formatted_chunks), []

def _resolve_rendered_text(post: Post, rendered_text: str, parse_mode: str | None) -> tuple[str, str | None]:
    if parse_mode is not None:
        return rendered_text, parse_mode
    if post.text_parse_mode == "HTML":
        return PostFormatter.compose_publish_html(post), "HTML"
    return rendered_text, None

def build_display_name(user) -> str:
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    if getattr(user, "username", None):
        return f"@{user.username}"
    return f"id{user.id}"







def _strip_submission_tags_from_formatted_text(formatted_text: str) -> str:
        if not formatted_text:
            return ""
        parts: list[str] = []
        last_index = 0
        previous_tag_end: int | None = None
        for match in PostParser.TAG_PATTERN.finditer(formatted_text):
            start, end = match.span()
            previous_char = formatted_text[start - 1] if start > 0 else ""
            starts_new_tag = (
                start == 0
                or not (previous_char.isalnum() or previous_char == "_")
                or previous_tag_end == start
            )
            if not starts_new_tag:
                previous_tag_end = None
                continue
            parts.append(formatted_text[last_index:start])
            last_index = end
            previous_tag_end = end
        parts.append(formatted_text[last_index:])
        return PostParser._normalize_submission_text("".join(parts))



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
    post = create_post_from_message(message)
    post.text = content.clean_text
    if post.formatted_text:
        post.formatted_text = _strip_submission_tags_from_formatted_text(post.formatted_text)
    post.public_tags = list(content.public_tags)
    post.is_anonymous = content.is_anonymous
    post.is_question = content.is_question
    post.wants_ai = content.wants_ai
    return post


def _build_platform_post_from_album(items: list, content: SubmissionContent) -> Post:
    post = create_post_from_media_group(items)
    post.text = content.clean_text
    if post.formatted_text:
        post.formatted_text = _strip_submission_tags_from_formatted_text(post.formatted_text)
    post.public_tags = list(content.public_tags)
    post.is_anonymous = content.is_anonymous
    post.is_question = content.is_question
    post.wants_ai = content.wants_ai
    return post


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def safe_delete_message(chat_id: int, message_id: int, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            await _maybe_await(predlojka_bot.delete_message(chat_id, message_id))
            return True
        except Exception as error:
            logger.error(f"Ошибка при удалении сообщения {message_id} (попытка {attempt + 1}): {error}")
            await asyncio.sleep(0.4)
    return False


async def safe_send_media_group(chat_id: int, media: list, max_retries: int = 3) -> list | None:
    for attempt in range(max_retries):
        try:
            return await _maybe_await(predlojka_bot.send_media_group(chat_id, media))
        except Exception as error:
            logger.error(f"Ошибка при отправке медиагруппы (попытка {attempt + 1}): {error}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
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

    match mes_type:
        case '!':
            if FUN < 0.9:
                return TEXT("thx", time, "variants_v", name=user_name)
            elif FUN >= 0.98:
                return TEXT("thx", time, "podval_variants_v", name=user_name)
            else:
                return TEXT("thx", time, "secret_variants_v", name=user_name)

        case '?':
            return TEXT("thx", time, "variants_q", name=user_name)

        case 'event':
            return TEXT("thx", time, "events_variants")

        case 'report':
            return TEXT("thx", time, "report_variants")

        case 'message':
            return TEXT("thx", time, "message_variants")

        case _:
            return TEXT("thx", time, "variants_v", name=user_name)
    

def _resolve_telegram_reference(attachment: MediaAttachment) -> str | None:
        telegram_ref = attachment.get_reference(Platform.TELEGRAM)
        if telegram_ref:
            return telegram_ref
        vk_ref = attachment.get_reference(Platform.VK)
        if vk_ref and vk_ref.startswith(("http://", "https://")):
            return vk_ref
        return None

def _build_album_media(self, post: Post, rendered_text: str, parse_mode: str | None = None) -> list:
    media = []
    for index, attachment in enumerate(post.attachments):
        file_id = self._resolve_telegram_reference(attachment)
        if not file_id:
            continue
        caption = rendered_text if index == 0 else None
        if attachment.media_type == MediaType.PHOTO:
            media.append(types.InputMediaPhoto(file_id, caption=caption, parse_mode=parse_mode))
        elif attachment.media_type == MediaType.VIDEO:
            media.append(types.InputMediaVideo(file_id, caption=caption, parse_mode=parse_mode))
    return media
