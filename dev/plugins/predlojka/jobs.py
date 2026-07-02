from __future__ import annotations

import threading

from dev.core.core_plugin.stats import log_event
from database.scheduled_posts_db import get_due_scheduled_posts, remove_scheduled_post

from . import handlers


scheduled_publish_lock = threading.Lock()


def publish_due_scheduled_posts() -> None:
    if not scheduled_publish_lock.acquire(blocking=False):
        return

    try:
        due_posts = get_due_scheduled_posts()
        for record in due_posts:
            try:
                if record["content_type"] == "album":
                    handlers._publish_album_payload(record["payload"])
                else:
                    handlers._publish_payload(record["payload"])
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
                handlers.logger.error(f"Не удалось опубликовать отложенную запись {record['doc_id']}: {error}")
                try:
                    handlers.predlojka_telegram_adapter.send_message(
                        handlers.admin,
                        "Не удалось опубликовать отложенную запись.\n"
                        f"ID задачи: {record['doc_id']}\n"
                        f"Тип: {record['content_type']}\n"
                        f"Ошибка: {error}",
                    )
                except Exception as notify_error:
                    handlers.logger.error(
                        f"Не удалось отправить уведомление админу о сбое отложенной записи {record['doc_id']}: {notify_error}"
                    )
    finally:
        scheduled_publish_lock.release()
