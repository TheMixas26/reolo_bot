from __future__ import annotations

from abc import ABC, abstractmethod

from posting.models import Platform, Post, PostTarget, PublishResult


class SocialAdapter(ABC):
    platform: Platform

    @abstractmethod
    def publish_post(
        self,
        target: PostTarget,
        post: Post,
        rendered_text: str,
        *,
        disable_notification: bool = False,
        parse_mode: str | None = None,
    ) -> PublishResult:
        """Публикует подготовленный пост в целевую платформу."""
