from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Platform(StrEnum):
    TELEGRAM = "telegram"
    VK = "vk"


class MediaType(StrEnum):
    TEXT = "text"
    STICKER = "sticker"
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"
    VOICE = "voice"


@dataclass(slots=True)
class PostAuthor:
    user_id: int | str
    display_name: str
    username: str | None = None


@dataclass(slots=True)
class PostOrigin:
    platform: Platform
    chat_id: int | str
    user_id: int | str
    message_id: int | str | None = None
    media_group_id: str | None = None


@dataclass(slots=True)
class MediaAttachment:
    media_type: MediaType
    references: dict[Platform, str] = field(default_factory=dict)
    file_name: str | None = None

    def get_reference(self, platform: Platform) -> str | None:
        return self.references.get(platform)

    def set_reference(self, platform: Platform, value: str) -> None:
        self.references[platform] = value


@dataclass(slots=True)
class Post:
    author: PostAuthor
    origin: PostOrigin
    text: str = ""
    public_tags: list[str] = field(default_factory=list)
    is_anonymous: bool = False
    is_question: bool = False
    wants_ai: bool = False
    append_author_signature: bool = True
    attachments: list[MediaAttachment] = field(default_factory=list)

    @property
    def has_media(self) -> bool:
        return bool(self.attachments)

    @property
    def is_album(self) -> bool:
        return len(self.attachments) > 1

    @property
    def primary_media_type(self) -> MediaType:
        if not self.attachments:
            return MediaType.TEXT
        return self.attachments[0].media_type

    @property
    def content_type_label(self) -> str:
        if self.is_album:
            return "album"
        return self.primary_media_type.value


@dataclass(slots=True)
class PostTarget:
    platform: Platform
    destination_id: int | str
    name: str


@dataclass(slots=True)
class PublishResult:
    platform: Platform
    target_id: int | str
    message_ids: list[int | str] = field(default_factory=list)
    raw_response: Any = None


@dataclass(slots=True)
class PublishOutcome:
    results: dict[Platform, PublishResult] = field(default_factory=dict)
    errors: dict[Platform, str] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def is_successful(self) -> bool:
        return bool(self.results) and not self.errors
