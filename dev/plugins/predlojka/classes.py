from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import html, re


VK_USER_ID_OFFSET = 10**12

TAG_ALIASES = {
    "#анон": "#anon",
    "#аноним": "#anon",
    "#anon": "#anon",
    "#вопрос": "#question",
    "#question": "#question",
    "#ai": "#ai",
    "#ignore": "#ignore",
    "#event": "#event",
    "#report": "#report",
    "#message": "#message",
    "#dm": "#message",
}
CONTROL_TAGS = {
    "#anon": "is_anonymous",
    "#question": "is_question",
    "#ai": "wants_ai",
    "#ignore": "ignore_reaction",
    "#event": "route_event",
    "#report": "route_report",
    "#message": "route_message",
}
TAG_PATTERN = re.compile(r"#[\wа-яА-ЯёЁ]+", re.UNICODE)



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
    formatted_text: str | None = None
    text_parse_mode: str | None = None
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


@dataclass(slots=True)
class ParsedSubmission:
    clean_text: str
    public_tags: list[str]
    is_anonymous: bool
    is_question: bool
    wants_ai: bool
    ignore_reaction: bool
    route: str


class PostParser:
    TAG_PATTERN = TAG_PATTERN

    @staticmethod
    def _normalize_submission_text(text: str) -> str:
        normalized = re.sub(r"[ \t]+", " ", text)
        normalized = re.sub(r" *\n *", "\n", normalized)
        normalized = re.sub(r" +([,.;:!?])", r"\1", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def parse_submission_text(text: str | None) -> ParsedSubmission:
        raw_text = text or ""
        public_tags: list[str] = []
        seen_tags: set[str] = set()
        flags = {
            "is_anonymous": False,
            "is_question": False,
            "wants_ai": False,
            "ignore_reaction": False,
            "route_event": False,
            "route_report": False,
            "route_message": False,
        }

        def _handle_tag(tag: str) -> None:
            canonical = TAG_ALIASES.get(tag, tag)
            flag_name = CONTROL_TAGS.get(canonical)
            if flag_name:
                flags[flag_name] = True
            elif canonical not in seen_tags:
                seen_tags.add(canonical)
                public_tags.append(canonical)

        parts: list[str] = []
        last_index = 0
        previous_tag_end: int | None = None
        for match in TAG_PATTERN.finditer(raw_text):
            start, end = match.span()
            previous_char = raw_text[start - 1] if start > 0 else ""
            starts_new_tag = (
                start == 0
                or not (previous_char.isalnum() or previous_char == "_")
                or previous_tag_end == start
            )
            if not starts_new_tag:
                previous_tag_end = None
                continue

            parts.append(raw_text[last_index:start])
            _handle_tag(match.group(0).lower())
            last_index = end
            previous_tag_end = end

        parts.append(raw_text[last_index:])
        clean_text = "".join(parts)
        clean_text = PostParser._normalize_submission_text(clean_text)

        route = "post"
        if flags["route_message"]:
            route = "message"
        elif flags["route_report"]:
            route = "report"
        elif flags["route_event"]:
            route = "event"

        return ParsedSubmission(
            clean_text=clean_text,
            public_tags=public_tags,
            is_anonymous=flags["is_anonymous"],
            is_question=flags["is_question"] and route == "post",
            wants_ai=flags["wants_ai"],
            ignore_reaction=flags["ignore_reaction"],
            route=route,
        )


class PostFactory:
    @staticmethod
    def create_submission_post(
        *,
        author: PostAuthor,
        origin: PostOrigin,
        raw_text: str | None,
        attachments: list[MediaAttachment] | None = None,
        append_author_signature: bool = True,
    ) -> Post:
        parsed = PostParser.parse_submission_text(raw_text)
        return Post(
            author=author,
            origin=origin,
            text=parsed.clean_text,
            public_tags=parsed.public_tags,
            is_anonymous=parsed.is_anonymous,
            is_question=parsed.is_question,
            wants_ai=parsed.wants_ai,
            append_author_signature=append_author_signature,
            attachments=list(attachments or []),
        )

    @staticmethod
    def create_raw_post(
        *,
        author: PostAuthor,
        origin: PostOrigin,
        text: str,
        attachments: list[MediaAttachment] | None = None,
        append_author_signature: bool = False,
    ) -> Post:
        return Post(
            author=author,
            origin=origin,
            text=text.strip(),
            append_author_signature=append_author_signature,
            attachments=list(attachments or []),
        )

    @staticmethod
    def create_system_post(
        *,
        platform: Platform,
        destination_id: int | str,
        text: str,
        display_name: str,
    ) -> Post:
        return Post(
            author=PostAuthor(user_id="system", display_name=display_name),
            origin=PostOrigin(platform=platform, chat_id=destination_id, user_id="system"),
            text=text.strip(),
            append_author_signature=False,
        )


class PostFormatter:
    @staticmethod
    def compose_publish_text(post: Post) -> str:
        parts: list[str] = []
        if post.text:
            parts.append(post.text)
        if post.public_tags:
            parts.append("🏷️ " + " ".join(post.public_tags))
        if post.append_author_signature:
            parts.append("🤫 Аноним" if post.is_anonymous else f"👤 {post.author.display_name}")
        return "\n\n".join(parts).strip()

    @staticmethod
    def compose_publish_html(post: Post) -> str:
        parts: list[str] = []
        if post.formatted_text:
            parts.append(post.formatted_text)
        elif post.text:
            parts.append(html.escape(post.text))
        if post.public_tags:
            parts.append(html.escape("🏷️ " + " ".join(post.public_tags)))
        if post.append_author_signature:
            signature = "🤫 Аноним" if post.is_anonymous else f"👤 {post.author.display_name}"
            parts.append(html.escape(signature))
        return "\n\n".join(parts).strip()

    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        escaped = text or ""
        for char in ("\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
            escaped = escaped.replace(char, f"\\{char}")
        return escaped

    @classmethod
    def format_markdown_quote(cls, text: str) -> str:
        lines = (text or "").splitlines() or [""]
        return "\n".join(f"> {cls.escape_markdown_v2(line)}" if line else ">" for line in lines)

    @staticmethod
    def fallback_question_text(post: Post) -> str:
        mapping = {
            "sticker": "Пользователь прислал вопрос в виде стикера.",
            "photo": "Пользователь прислал вопрос вместе с фотографией.",
            "video": "Пользователь прислал вопрос вместе с видео.",
            "document": "Пользователь прислал вопрос вместе с документом.",
            "audio": "Пользователь прислал вопрос вместе с аудио.",
            "voice": "Пользователь прислал вопрос голосовым сообщением.",
            "album": "Пользователь прислал вопрос вместе с альбомом.",
        }
        return mapping.get(post.content_type_label, "Пользователь прислал вопрос в необычном формате.")

    @classmethod
    def build_question_answer_post(cls, post: Post, answer_text: str) -> str:
        question_text = post.text.strip() or cls.fallback_question_text(post)
        author_line = "🤫 Анонимный вопрос" if post.is_anonymous else f"👤 Вопрос от {post.author.display_name}"
        parts = [
            "❓ *ВОПРОС ПОДПИСЧИКА*",
            cls.escape_markdown_v2(author_line),
            "",
            "*Вопрос*",
            cls.format_markdown_quote(question_text),
            "",
            "*Ответ администрации*",
            cls.format_markdown_quote(answer_text.strip()),
        ]

        if post.public_tags:
            parts.extend(["", "*Теги*", cls.escape_markdown_v2(" ".join(post.public_tags))])

        return "\n".join(parts)


class PostPublisher:
    def __init__(self, adapters, targets: list[PostTarget]) -> None:
        self.adapters = adapters
        self.targets = targets

    def publish_post(
        self,
        post: Post,
        *,
        rendered_text: str,
        disable_notification: bool = False,
        parse_mode: str | None = None,
    ) -> PublishOutcome:
        results: dict[Platform, PublishResult] = {}
        errors: dict[Platform, str] = {}

        for target in self.targets:
            adapter = self.adapters.get(target.platform)
            if adapter is None:
                continue
            try:
                results[target.platform] = adapter.publish_post(
                    target,
                    post,
                    rendered_text,
                    disable_notification=disable_notification,
                    parse_mode=parse_mode,
                )
            except Exception as error:
                errors[target.platform] = f"{target.name} ({target.platform.value}): {error}"

        if not results and errors:
            raise RuntimeError("; ".join(errors.values()))

        return PublishOutcome(results=results, errors=errors)


def to_storage_user_id(platform: Platform, user_id: int | str) -> int:
    numeric_user_id = int(user_id)
    if platform == Platform.VK:
        return VK_USER_ID_OFFSET + numeric_user_id
    return numeric_user_id
