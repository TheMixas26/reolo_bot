from __future__ import annotations

import re
from dataclasses import dataclass

from posting.adapters.base import SocialAdapter
from posting.models import MediaAttachment, Platform, Post, PostAuthor, PostOrigin, PostTarget, PublishOutcome, PublishResult

CONTROL_TAGS = {"#анон": "is_anonymous", "#вопрос": "is_question", "#ai": "wants_ai"}
TAG_PATTERN = re.compile(r"(?<!\w)#[\wа-яА-ЯёЁ]+", re.UNICODE)


@dataclass(slots=True)
class ParsedSubmission:
    clean_text: str
    public_tags: list[str]
    is_anonymous: bool
    is_question: bool
    wants_ai: bool


class PostParser:
    @staticmethod
    def parse_submission_text(text: str | None) -> ParsedSubmission:
        raw_text = text or ""
        public_tags: list[str] = []
        seen_tags: set[str] = set()
        flags = {"is_anonymous": False, "is_question": False, "wants_ai": False}

        def _replace_tag(match: re.Match[str]) -> str:
            tag = match.group(0).lower()
            flag_name = CONTROL_TAGS.get(tag)
            if flag_name:
                flags[flag_name] = True
            elif tag not in seen_tags:
                seen_tags.add(tag)
                public_tags.append(tag)
            return ""

        clean_text = TAG_PATTERN.sub(_replace_tag, raw_text)
        clean_text = re.sub(r"[ \t]+", " ", clean_text)
        clean_text = re.sub(r" *\n *", "\n", clean_text)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

        return ParsedSubmission(
            clean_text=clean_text,
            public_tags=public_tags,
            is_anonymous=flags["is_anonymous"],
            is_question=flags["is_question"],
            wants_ai=flags["wants_ai"],
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
    def __init__(self, adapters: dict[Platform, SocialAdapter], targets: list[PostTarget]) -> None:
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
