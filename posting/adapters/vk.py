from __future__ import annotations

import mimetypes
import random
import time
from pathlib import Path

import requests

from posting.adapters.base import SocialAdapter
from posting.models import MediaAttachment, MediaType, Platform, Post, PostAuthor, PostOrigin, PostTarget, PublishResult
from posting.services import PostFactory


class VKAdapter(SocialAdapter):
    platform = Platform.VK

    def __init__(
        self,
        token: str,
        *,
        api_version: str = "5.199",
        timeout: int = 20,
        group_id: int | None = None,
        telegram_adapter=None,
    ) -> None:
        self.token = token
        self.api_version = api_version
        self.timeout = timeout
        self.group_id = int(group_id) if group_id else None
        self.telegram_adapter = telegram_adapter
        self._user_cache: dict[int, dict] = {}

    def _call_api(self, method: str, **params):
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data={**params, "access_token": self.token, "v": self.api_version},
            timeout=self.timeout,
        )
        payload = response.json()
        if "error" in payload:
            error = payload["error"]
            raise RuntimeError(f"VK API error {error.get('error_code')}: {error.get('error_msg')}")
        return payload["response"]

    @staticmethod
    def _build_vk_attachment_id(prefix: str, owner_id: int, item_id: int) -> str:
        return f"{prefix}{owner_id}_{item_id}"

    def send_message(self, peer_id: int, text: str) -> None:
        self._call_api(
            "messages.send",
            peer_id=peer_id,
            random_id=random.randint(1, 2**31 - 1),
            message=text,
        )

    def get_user(self, user_id: int) -> dict:
        cached = self._user_cache.get(user_id)
        if cached is not None:
            return cached

        response = self._call_api("users.get", user_ids=user_id)
        user = response[0]
        self._user_cache[user_id] = user
        return user

    def build_display_name(self, user_id: int) -> str:
        user = self.get_user(user_id)
        full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        return full_name or f"id{user_id}"

    def listen(self):
        if not self.group_id:
            raise RuntimeError("VK_GROUP_ID не настроен")

        server_info = self._call_api("groups.getLongPollServer", group_id=self.group_id)
        server = server_info["server"]
        key = server_info["key"]
        ts = server_info["ts"]

        while True:
            response = requests.get(
                server,
                params={"act": "a_check", "key": key, "ts": ts, "wait": 25},
                timeout=self.timeout + 10,
            ).json()

            failed = response.get("failed")
            if failed:
                server_info = self._call_api("groups.getLongPollServer", group_id=self.group_id)
                server = server_info["server"]
                key = server_info["key"]
                ts = server_info["ts"]
                continue

            ts = response["ts"]
            for update in response.get("updates", []):
                yield update

    def create_post_from_event(self, event: dict) -> Post:
        message = event["object"]["message"]
        user_id = int(message["from_id"])
        peer_id = int(message["peer_id"])
        text = message.get("text") or ""
        attachments = self._extract_message_attachments(message.get("attachments", []))
        author = PostAuthor(
            user_id=user_id,
            display_name=self.build_display_name(user_id),
        )
        origin = PostOrigin(
            platform=Platform.VK,
            chat_id=peer_id,
            user_id=user_id,
            message_id=message.get("id"),
        )
        return PostFactory.create_submission_post(author=author, origin=origin, raw_text=text, attachments=attachments)

    def _extract_message_attachments(self, raw_attachments: list[dict]) -> list[MediaAttachment]:
        attachments: list[MediaAttachment] = []
        for raw_attachment in raw_attachments:
            attachment_type = raw_attachment.get("type")
            if attachment_type == "photo":
                photo = raw_attachment["photo"]
                sizes = photo.get("sizes") or []
                url = ""
                if sizes:
                    url = max(sizes, key=lambda item: item.get("width", 0) * item.get("height", 0)).get("url", "")
                attachments.append(
                    MediaAttachment(
                        media_type=MediaType.PHOTO,
                        references={
                            Platform.VK: self._build_vk_attachment_id("photo", int(photo["owner_id"]), int(photo["id"])),
                            Platform.TELEGRAM: url,
                        },
                    )
                )
            elif attachment_type == "doc":
                document = raw_attachment["doc"]
                ext = str(document.get("ext") or "").lower()
                media_type = MediaType.VOICE if ext in {"ogg"} else MediaType.DOCUMENT
                attachments.append(
                    MediaAttachment(
                        media_type=media_type,
                        references={
                            Platform.VK: self._build_vk_attachment_id("doc", int(document["owner_id"]), int(document["id"])),
                            Platform.TELEGRAM: document.get("url", ""),
                        },
                        file_name=document.get("title"),
                    )
                )
            elif attachment_type == "video":
                video = raw_attachment["video"]
                telegram_url = ""
                files = video.get("files") or {}
                for key in ("mp4_720", "mp4_480", "mp4_360", "external"):
                    if files.get(key):
                        telegram_url = files[key]
                        break
                attachments.append(
                    MediaAttachment(
                        media_type=MediaType.VIDEO,
                        references={
                            Platform.VK: self._build_vk_attachment_id("video", int(video["owner_id"]), int(video["id"])),
                            Platform.TELEGRAM: telegram_url,
                        },
                        file_name=video.get("title"),
                    )
                )
            elif attachment_type == "sticker":
                sticker = raw_attachment["sticker"]
                images = sticker.get("images") or sticker.get("images_with_background") or []
                sticker_url = ""
                if images:
                    sticker_url = max(images, key=lambda item: item.get("width", 0) * item.get("height", 0)).get("url", "")
                attachments.append(
                    MediaAttachment(
                        media_type=MediaType.PHOTO,
                        references={Platform.TELEGRAM: sticker_url},
                        file_name=f"sticker_{sticker.get('sticker_id', 'vk')}.png",
                    )
                )
        return attachments

    def _download_attachment(self, attachment: MediaAttachment) -> tuple[bytes, str, str]:
        source_ref = attachment.get_reference(Platform.TELEGRAM)
        if not source_ref:
            raise RuntimeError("Attachment has no downloadable reference")

        if source_ref.startswith(("http://", "https://")):
            response = requests.get(source_ref, timeout=self.timeout)
            response.raise_for_status()
            content = response.content
            file_name = attachment.file_name or Path(source_ref.split("?")[0]).name or f"attachment_{int(time.time())}"
        else:
            if self.telegram_adapter is None:
                raise RuntimeError("Telegram adapter is required for TG -> VK media sync")
            file_info = self.telegram_adapter.bot.get_file(source_ref)
            content = self.telegram_adapter.bot.download_file(file_info.file_path)
            file_name = attachment.file_name or Path(file_info.file_path).name or f"attachment_{int(time.time())}"

        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        return content, file_name, mime_type

    def _upload_bytes(self, upload_url: str, field_name: str, *, content: bytes, file_name: str, mime_type: str) -> dict:
        response = requests.post(
            upload_url,
            files={field_name: (file_name, content, mime_type)},
            timeout=self.timeout,
        )
        return response.json()

    def _upload_photo_to_vk(self, attachment: MediaAttachment, *, owner_id: int) -> str:
        content, file_name, mime_type = self._download_attachment(attachment)
        params = {}
        if owner_id < 0:
            params["group_id"] = abs(owner_id)
        upload_info = self._call_api("photos.getWallUploadServer", **params)
        upload_result = self._upload_bytes(upload_info["upload_url"], "photo", content=content, file_name=file_name, mime_type=mime_type)
        save_params = {
            "photo": upload_result["photo"],
            "server": upload_result["server"],
            "hash": upload_result["hash"],
        }
        if owner_id < 0:
            save_params["group_id"] = abs(owner_id)
        saved = self._call_api("photos.saveWallPhoto", **save_params)[0]
        return self._build_vk_attachment_id("photo", int(saved["owner_id"]), int(saved["id"]))

    def _upload_doc_to_vk(self, attachment: MediaAttachment, *, owner_id: int) -> str:
        content, file_name, mime_type = self._download_attachment(attachment)
        params = {}
        if owner_id < 0:
            params["group_id"] = abs(owner_id)
        upload_info = self._call_api("docs.getWallUploadServer", **params)
        upload_result = self._upload_bytes(upload_info["upload_url"], "file", content=content, file_name=file_name, mime_type=mime_type)
        saved = self._call_api("docs.save", file=upload_result["file"], title=file_name)

        if isinstance(saved, list):
            document = saved[0]
        else:
            document = saved.get("doc") or saved.get("audio_message") or saved

        return self._build_vk_attachment_id("doc", int(document["owner_id"]), int(document["id"]))

    def _ensure_vk_reference(self, attachment: MediaAttachment, *, owner_id: int) -> str | None:
        existing = attachment.get_reference(Platform.VK)
        if existing:
            return existing

        if not attachment.get_reference(Platform.TELEGRAM):
            return None

        if attachment.media_type == MediaType.PHOTO:
            uploaded = self._upload_photo_to_vk(attachment, owner_id=owner_id)
        else:
            uploaded = self._upload_doc_to_vk(attachment, owner_id=owner_id)

        attachment.set_reference(Platform.VK, uploaded)
        return uploaded

    def _extract_vk_attachments(self, post: Post, *, owner_id: int) -> list[str]:
        attachment_ids: list[str] = []
        for attachment in post.attachments:
            reference = self._ensure_vk_reference(attachment, owner_id=owner_id)
            if reference:
                attachment_ids.append(reference)
        return attachment_ids

    def publish_post(
        self,
        target: PostTarget,
        post: Post,
        rendered_text: str,
        *,
        disable_notification: bool = False,
        parse_mode: str | None = None,
    ) -> PublishResult:
        owner_id = int(target.destination_id)
        payload = {
            "owner_id": owner_id,
            "from_group": 1 if owner_id < 0 else 0,
            "message": rendered_text,
        }
        attachment_ids = self._extract_vk_attachments(post, owner_id=owner_id)
        if attachment_ids:
            payload["attachments"] = ",".join(attachment_ids)

        response = self._call_api("wall.post", **payload)
        return PublishResult(
            platform=self.platform,
            target_id=target.destination_id,
            message_ids=[response.get("post_id")],
            raw_response=response,
        )
