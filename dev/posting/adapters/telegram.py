from __future__ import annotations

from telebot import types

from posting.adapters.base import SocialAdapter
from posting.models import MediaAttachment, MediaType, Platform, Post, PostAuthor, PostOrigin, PostTarget, PublishResult
from posting.services import PostFactory


class TelegramAdapter(SocialAdapter):
    platform = Platform.TELEGRAM

    def __init__(self, bot) -> None:
        self.bot = bot

    @staticmethod
    def build_display_name(user) -> str:
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            return full_name
        if getattr(user, "username", None):
            return f"@{user.username}"
        return f"id{user.id}"

    def create_post_from_message(self, message, *, append_author_signature: bool = True) -> Post:
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

        raw_text = message.text if content_type == "text" else message.caption
        author = PostAuthor(
            user_id=message.from_user.id,
            display_name=self.build_display_name(message.from_user),
            username=getattr(message.from_user, "username", None),
        )
        origin = PostOrigin(
            platform=Platform.TELEGRAM,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            message_id=message.message_id,
            media_group_id=getattr(message, "media_group_id", None),
        )
        return PostFactory.create_submission_post(
            author=author,
            origin=origin,
            raw_text=raw_text,
            attachments=attachments,
            append_author_signature=append_author_signature,
        )

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
        return PostFactory.create_submission_post(author=author, origin=origin, raw_text=raw_text, attachments=attachments)

    def send_text(self, chat_id: int | str, text: str, **kwargs):
        return self.bot.send_message(chat_id, text, **kwargs)

    def reply_to(self, message, text: str, **kwargs):
        return self.bot.reply_to(message, text, **kwargs)

    def edit_message_text(self, text: str, *, chat_id: int | str, message_id: int | str, **kwargs):
        return self.bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, **kwargs)

    def answer_callback_query(self, callback_id: str, text: str):
        return self.bot.answer_callback_query(callback_id, text)

    def register_next_step_handler(self, message, callback, *args):
        return self.bot.register_next_step_handler(message, callback, *args)

    def delete_message(self, chat_id: int | str, message_id: int | str):
        return self.bot.delete_message(chat_id, message_id)

    @staticmethod
    def _resolve_telegram_reference(attachment: MediaAttachment) -> str | None:
        telegram_ref = attachment.get_reference(Platform.TELEGRAM)
        if telegram_ref:
            return telegram_ref
        vk_ref = attachment.get_reference(Platform.VK)
        if vk_ref and vk_ref.startswith(("http://", "https://")):
            return vk_ref
        return None

    def _build_album_media(self, post: Post, rendered_text: str) -> list:
        media = []
        for index, attachment in enumerate(post.attachments):
            file_id = self._resolve_telegram_reference(attachment)
            if not file_id:
                continue
            caption = rendered_text if index == 0 else None
            if attachment.media_type == MediaType.PHOTO:
                media.append(types.InputMediaPhoto(file_id, caption=caption))
            elif attachment.media_type == MediaType.VIDEO:
                media.append(types.InputMediaVideo(file_id, caption=caption))
        return media

    def publish_post(
        self,
        target: PostTarget,
        post: Post,
        rendered_text: str,
        *,
        disable_notification: bool = False,
        parse_mode: str | None = None,
    ) -> PublishResult:
        message_ids: list[int | str] = []

        if post.is_album:
            media = self._build_album_media(post, rendered_text)
            if not media:
                response = self.bot.send_message(
                    target.destination_id,
                    rendered_text,
                    disable_notification=disable_notification,
                    parse_mode=parse_mode,
                )
                return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=[response.message_id], raw_response=response)
            response = self.bot.send_media_group(target.destination_id, media)
            message_ids.extend(item.message_id for item in response)
            return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=message_ids, raw_response=response)

        if not post.attachments:
            response = self.bot.send_message(
                target.destination_id,
                rendered_text,
                disable_notification=disable_notification,
                parse_mode=parse_mode,
            )
            return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=[response.message_id], raw_response=response)

        attachment = post.attachments[0]
        file_id = self._resolve_telegram_reference(attachment)
        if not file_id:
            response = self.bot.send_message(
                target.destination_id,
                rendered_text,
                disable_notification=disable_notification,
                parse_mode=parse_mode,
            )
            return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=[response.message_id], raw_response=response)

        if attachment.media_type == MediaType.STICKER:
            sticker_message = self.bot.send_sticker(target.destination_id, file_id, disable_notification=disable_notification)
            message_ids.append(sticker_message.message_id)
            if rendered_text:
                text_message = self.bot.send_message(
                    target.destination_id,
                    rendered_text,
                    disable_notification=disable_notification,
                    parse_mode=parse_mode,
                )
                message_ids.append(text_message.message_id)
                return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=message_ids, raw_response=[sticker_message, text_message])
            return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=message_ids, raw_response=sticker_message)

        sender_map = {
            MediaType.PHOTO: self.bot.send_photo,
            MediaType.VIDEO: self.bot.send_video,
            MediaType.DOCUMENT: self.bot.send_document,
            MediaType.AUDIO: self.bot.send_audio,
            MediaType.VOICE: self.bot.send_voice,
        }
        sender = sender_map.get(attachment.media_type)
        if sender is None:
            raise ValueError(f"Неподдерживаемый тип публикации в Telegram: {attachment.media_type.value}")

        response = sender(
            target.destination_id,
            file_id,
            caption=rendered_text or None,
            disable_notification=disable_notification,
            parse_mode=parse_mode,
        )
        return PublishResult(platform=self.platform, target_id=target.destination_id, message_ids=[response.message_id], raw_response=response)
