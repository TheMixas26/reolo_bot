from __future__ import annotations

import json
from datetime import datetime

from .connection import execute, fetch, fetchval


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime(DATETIME_FORMAT)


def deserialize_datetime(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.strptime(value, DATETIME_FORMAT)


def _row_to_record(row) -> dict:
    record = dict(row)
    record["doc_id"] = record.pop("id")
    payload = record.get("payload")
    if isinstance(payload, str):
        record["payload"] = json.loads(payload)
    return record


async def create_scheduled_post(
    *,
    payload: dict,
    content_type: str,
    publish_at: datetime | None,
    is_question: bool,
    is_anonymous: bool,
    source_user_id: int,
    status: str = "scheduled",
    created_by: int | None = None,
):
    return await fetchval(
        """
        INSERT INTO scheduled_posts(
            payload, content_type, publish_at, is_question, is_anonymous,
            source_user_id, status, created_by
        )
        VALUES ($1::jsonb, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        json.dumps(payload, ensure_ascii=False),
        content_type,
        publish_at,
        is_question,
        is_anonymous,
        source_user_id,
        status,
        created_by,
    )


async def list_scheduled_posts(*, statuses: list[str] | None = None, limit: int = 20) -> list[dict]:
    statuses = statuses or ["draft", "scheduled"]
    rows = await fetch(
        """
        SELECT *
        FROM scheduled_posts
        WHERE status = ANY($1::text[])
        ORDER BY
            CASE WHEN status = 'scheduled' THEN 0 ELSE 1 END,
            COALESCE(publish_at, TIMESTAMP '9999-12-31 23:59:59'),
            created_at
        LIMIT $2
        """,
        statuses,
        limit,
    )
    return [_row_to_record(row) for row in rows]


async def get_due_scheduled_posts(now: datetime | None = None) -> list[dict]:
    rows = await fetch(
        """
        SELECT *
        FROM scheduled_posts
        WHERE status = 'scheduled'
            AND publish_at IS NOT NULL
            AND publish_at <= $1
        ORDER BY publish_at
        """,
        now or datetime.now(),
    )
    return [_row_to_record(row) for row in rows]


async def remove_scheduled_post(doc_id: int) -> None:
    await execute("DELETE FROM scheduled_posts WHERE id = $1", doc_id)
