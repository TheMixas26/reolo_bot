from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass

from telebot import types

from ai.ai_module import stream_ai
from analytics.stats import log_event
from config import admin, channel, channel_red, chat_mishas_den
from database.sqlite_db import add_to_post_counter, create_user_if_missing, user_exists
from posting.models import Platform, Post
from posting.platform_ids import to_storage_user_id
from posting.runtime import post_publisher, telegram_adapter, telegram_admin_target
from posting.services import PostFormatter
from utils.utils import thx_for_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

predlojka_bot = telegram_adapter.bot
q = types.ReplyKeyboardRemove()
media_groups_buffer: dict[str, list] = {}
media_groups_timer: dict[str, threading.Timer] = {}
moderation_queue: dict[int, "ModerationEntry"] = {}
pending_question_answers: dict[int, "PendingQuestionAnswer"] = {}

MEDIA_GROUP_TIMEOUT = 2.0
BLOCKED_SUBMISSION_CHATS = {channel, channel_red, chat_mishas_den}


@dataclass(slots=True)
class ModerationEntry:
    post: Post
    preview_message_ids: list[int | str]


@dataclass(slots=True)
class PendingQuestionAnswer:
    entry: ModerationEntry
    moderation_message_id: int


def safe_delete_message(chat_id: int, message_id: int, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            telegram_adapter.delete_message(chat_id, message_id)
            return True
        except Exception as error:
            logger.error(f"Ошибка при удалении сообщения {message_id} (попытка {attempt + 1}): {error}")
            time.sleep(0.4)
    return False


def _can_use_ai(chat_id: int) -> bool:
    return chat_id == chat_mishas_den or chat_id not in BLOCKED_SUBMISSION_CHATS


def _can_submit_post(chat_id: int) -> bool:
    return chat_id not in BLOCKED_SUBMISSION_CHATS


def _preview_title(post: Post) -> str:
    flags = []
    if post.is_question:
        flags.append("вопрос")
    if post.is_anonymous:
        flags.append("анон")
    flags.append(post.content_type_label)
    return "Новая запись: " + ", ".join(flags)


def _build_moderation_markup(*, is_question: bool = False) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    approve_label = "Ответить и опубликовать" if is_question else "Опубликовать"
    markup.add(types.InlineKeyboardButton(approve_label, callback_data="mod:approve"))
    markup.add(types.InlineKeyboardButton("Отклонить", callback_data="mod:reject"))
    return markup


def _log_submission(post: Post, *, event_type: str) -> None:
    log_event(
        event_type,
        bot="predlojka",
        user_id=int(post.origin.user_id),
        chat_id=int(post.origin.chat_id),
        metadata={
            "source_platform": post.origin.platform.value,
            "content_type": post.content_type_label,
            "anonymous": post.is_anonymous,
            "tags": post.public_tags,
        },
    )


def _send_admin_preview(post: Post) -> None:
    preview_text = PostFormatter.compose_publish_text(post)
    preview_result = telegram_adapter.publish_post(telegram_admin_target, post, preview_text)

    control_lines = [_preview_title(post)]
    if post.is_album:
        control_lines.append(f"Медиафайлов: {len(post.attachments)}")

    control_message = telegram_adapter.send_text(
        admin,
        "\n\n".join(control_lines),
        reply_markup=_build_moderation_markup(is_question=post.is_question),
    )
    moderation_queue[control_message.message_id] = ModerationEntry(
        post=post,
        preview_message_ids=preview_result.message_ids,
    )


def _clear_preview_messages(entry: ModerationEntry, moderation_message_id: int | None = None) -> None:
    for preview_message_id in entry.preview_message_ids:
        safe_delete_message(admin, int(preview_message_id))
    if moderation_message_id is not None:
        safe_delete_message(admin, moderation_message_id)


def _notify_publish_warnings(errors: dict) -> None:
    if not errors:
        return
    warning_text = "Часть площадок не приняла публикацию:\n" + "\n".join(f"- {error}" for error in errors.values())
    telegram_adapter.send_text(admin, warning_text)


def _request_question_answer(call, entry: ModerationEntry) -> None:
    pending_question_answers[call.from_user.id] = PendingQuestionAnswer(
        entry=entry,
        moderation_message_id=call.message.message_id,
    )
    prompt = telegram_adapter.send_text(
        admin,
        "Отлично! Напиши ответ текстом, а я передам его в канал и в VK.\n\nЕсли передумал, напиши /cancel_question_answer",
        reply_to_message_id=call.message.message_id,
    )
    telegram_adapter.register_next_step_handler(prompt, handle_question_answer_input)
    telegram_adapter.answer_callback_query(call.id, "Жду текст ответа.")
    log_event(
        "question_answer_requested",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={
            "source_user_id": entry.post.origin.user_id,
            "content_type": entry.post.content_type_label,
        },
    )


def handle_question_answer_input(message):
    pending = pending_question_answers.get(message.from_user.id)
    if pending is None:
        telegram_adapter.reply_to(message, "Не могу найти вопроса, который ожидает ответа... (⊙▂⊙)")
        return

    if message.text and message.text.strip() == "/cancel_question_answer":
        moderation_queue[pending.moderation_message_id] = pending.entry
        pending_question_answers.pop(message.from_user.id, None)
        telegram_adapter.reply_to(message, "Как скажешь, вернула вопрос в очередь модерации.")
        return

    answer_text = (message.text or "").strip()
    if not answer_text:
        retry_prompt = telegram_adapter.reply_to(
            message,
            "Боюсь, я смогу принять только текст в качестве ответа... Увы (︶︹︶)",
        )
        telegram_adapter.register_next_step_handler(retry_prompt, handle_question_answer_input)
        return

    try:
        rendered_text = PostFormatter.build_question_answer_post(pending.entry.post, answer_text)
        outcome = post_publisher.publish_post(
            pending.entry.post,
            rendered_text=rendered_text,
            disable_notification=True,
            parse_mode="MarkdownV2",
        )
        _clear_preview_messages(pending.entry, pending.moderation_message_id)
        safe_delete_message(admin, message.message_id)
        pending_question_answers.pop(message.from_user.id, None)
        if outcome.has_errors:
            _notify_publish_warnings(outcome.errors)
            telegram_adapter.send_text(admin, "Вопрос опубликован, но не все площадки ответили без ошибок.")
        else:
            telegram_adapter.send_text(admin, "Вопрос с ответом опубликован в канале и отправлен во все активные площадки.")
        log_event(
            "question_approved",
            bot="predlojka",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={
                "source_user_id": pending.entry.post.origin.user_id,
                "content_type": pending.entry.post.content_type_label,
                "answer_length": len(answer_text),
            },
        )
        logger.info("Вопрос с ответом опубликован")
    except Exception as error:
        moderation_queue[pending.moderation_message_id] = pending.entry
        pending_question_answers.pop(message.from_user.id, None)
        logger.error(f"Ошибка при публикации вопроса с ответом: {error}")
        telegram_adapter.reply_to(message, "Не получилось опубликовать вопрос с ответом. Вернула его в очередь модерации.")


def _handle_ai_request(message, post: Post) -> None:
    prompt_text = post.text or (message.text or "")
    response_message = telegram_adapter.reply_to(message, "Думаю... (*￣3￣)╭")
    loop = None
    log_event("ai_requested", bot="predlojka", user_id=message.from_user.id, chat_id=message.chat.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _get_ai_response() -> str:
            full_response = ""
            async for chunk in stream_ai(prompt_text, post.author.display_name):
                full_response = chunk
            return full_response

        full_text = loop.run_until_complete(_get_ai_response())
        telegram_adapter.edit_message_text(full_text, chat_id=message.chat.id, message_id=response_message.message_id)
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
            telegram_adapter.edit_message_text(
                "Извините, что-то пошло не так... Попробуй ещё раз позже (^_^;)",
                chat_id=message.chat.id,
                message_id=response_message.message_id,
            )
        except Exception:
            telegram_adapter.send_text(message.chat.id, "Извините, ошибка обработки...")
    finally:
        if loop is not None:
            loop.close()


def _acknowledge_submission(message, post: Post) -> None:
    telegram_adapter.send_text(
        message.chat.id,
        thx_for_message(post.author.display_name, mes_type="?" if post.is_question else "!"),
        reply_markup=q,
    )


def _ensure_user_for_post(post: Post, *, first_name: str | None = None, last_name: str | None = None) -> int:
    storage_user_id = to_storage_user_id(post.origin.platform, post.origin.user_id)
    if not user_exists(storage_user_id):
        create_user_if_missing(storage_user_id, first_name or post.author.display_name, last_name)
    return storage_user_id


def submit_external_post(post: Post, *, acknowledge_callback=None) -> None:
    if post.origin.platform == Platform.TELEGRAM and not _can_submit_post(int(post.origin.chat_id)):
        return

    storage_user_id = _ensure_user_for_post(post)
    add_to_post_counter(storage_user_id)

    if acknowledge_callback is not None:
        acknowledge_callback(post)

    _send_admin_preview(post)
    _log_submission(post, event_type="question_submitted" if post.is_question else "post_submitted")
    logger.info(f"Получена запись для модерации: {post.content_type_label} ({post.origin.platform.value})")


def _submit_post(message, post: Post) -> None:
    if post.primary_media_type.value == "text" and post.wants_ai and _can_use_ai(message.chat.id):
        _handle_ai_request(message, post)
        return

    _ensure_user_for_post(post, first_name=message.from_user.first_name, last_name=message.from_user.last_name)
    submit_external_post(post, acknowledge_callback=lambda prepared_post: _acknowledge_submission(message, prepared_post))


@predlojka_bot.message_handler(content_types=["sticker", "text", "document", "audio", "voice"])
def accepter(message):
    if not user_exists(message.from_user.id):
        create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)

    if message.content_type == "text" and message.text.startswith("/"):
        telegram_adapter.reply_to(message, "Боюсь, такой команды я не знаю... (｡•́︿•̀｡)")
        return

    post = telegram_adapter.create_post_from_message(message)
    _submit_post(message, post)


def process_media_group_for_moderation(media_group_id: str) -> None:
    try:
        items = media_groups_buffer.pop(media_group_id, [])
        media_groups_timer.pop(media_group_id, None)
        if not items:
            return
        if not _can_submit_post(items[0].chat.id):
            return

        post = telegram_adapter.create_post_from_media_group(items)
        add_to_post_counter(post.origin.user_id)
        _acknowledge_submission(items[0], post)
        _send_admin_preview(post)

        log_event(
            "album_submitted",
            bot="predlojka",
            user_id=int(post.origin.user_id),
            chat_id=int(post.origin.chat_id),
            metadata={"count": len(post.attachments), "anonymous": post.is_anonymous, "tags": post.public_tags},
        )
        logger.info(f"Альбом {media_group_id} отправлен на модерацию")
    except Exception as error:
        logger.error(f"Критическая ошибка в process_media_group_for_moderation: {error}", exc_info=True)


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:approve")
def sender(call):
    entry = moderation_queue.pop(call.message.message_id, None)
    if entry is None:
        telegram_adapter.answer_callback_query(call.id, "Эта запись уже обработана или устарела... (◔~◔)")
        return

    if entry.post.is_question:
        _request_question_answer(call, entry)
        return

    try:
        outcome = post_publisher.publish_post(
            entry.post,
            rendered_text=PostFormatter.compose_publish_text(entry.post),
            disable_notification=True,
        )
        _clear_preview_messages(entry, call.message.message_id)
        if outcome.has_errors:
            _notify_publish_warnings(outcome.errors)
            telegram_adapter.answer_callback_query(call.id, "Опубликовано, но часть площадок вернула ошибку")
        else:
            telegram_adapter.answer_callback_query(call.id, "Сообщение опубликовано")
        log_event(
            "post_approved",
            bot="predlojka",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={
                "source_user_id": entry.post.origin.user_id,
                "content_type": entry.post.content_type_label,
            },
        )
        logger.info("Пост опубликован")
    except Exception as error:
        logger.error(f"Ошибка при публикации поста: {error}")
        telegram_adapter.answer_callback_query(call.id, "Ошибка при публикации")


@predlojka_bot.callback_query_handler(func=lambda call: call.data == "mod:reject")
def denier(call):
    entry = moderation_queue.pop(call.message.message_id, None)
    if entry is None:
        telegram_adapter.answer_callback_query(call.id, "Эта запись уже обработана или устарела.")
        return

    _clear_preview_messages(entry, call.message.message_id)
    telegram_adapter.answer_callback_query(call.id, "Сообщение отклонено")
    log_event(
        "question_rejected" if entry.post.is_question else "post_rejected",
        bot="predlojka",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={
            "source_user_id": entry.post.origin.user_id,
            "content_type": entry.post.content_type_label,
        },
    )
    logger.info("Пост отклонён")

@predlojka_bot.message_handler(content_types=["photo", "video"])
def media_group_handler(message):
    if not user_exists(message.from_user.id):
        create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)

    media_group_id = getattr(message, "media_group_id", None)
    if not media_group_id:
        post = telegram_adapter.create_post_from_message(message)
        _submit_post(message, post)
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
