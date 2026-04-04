from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock

from tinydb import Query, TinyDB

DB_PATH = Path("dev/database/posts.json")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_db = TinyDB(DB_PATH, ensure_ascii=False, indent=2)
_table = _db.table("scheduled_posts")
_query = Query()
_lock = Lock()

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime(DATETIME_FORMAT)


def deserialize_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, DATETIME_FORMAT)


def create_scheduled_post(
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
    record = {
        "payload": payload,
        "content_type": content_type,
        "publish_at": serialize_datetime(publish_at),
        "is_question": is_question,
        "is_anonymous": is_anonymous,
        "source_user_id": source_user_id,
        "status": status,
        "created_by": created_by,
        "created_at": serialize_datetime(datetime.now()),
    }
    with _lock:
        return _table.insert(record)


def list_scheduled_posts(*, statuses: list[str] | None = None, limit: int = 20) -> list[dict]:
    statuses = statuses or ["draft", "scheduled"]
    with _lock:
        rows = _table.search(_query.status.one_of(statuses))

    def _sort_key(item):
        status_weight = 0 if item.get("status") == "scheduled" else 1
        publish_at = item.get("publish_at") or "9999-99-99 99:99:99"
        created_at = item.get("created_at") or ""
        return (status_weight, publish_at, created_at)

    result = []
    for row in sorted(rows, key=_sort_key)[:limit]:
        result.append({"doc_id": row.doc_id, **dict(row)})
    return result



def get_due_scheduled_posts(now: datetime | None = None) -> list[dict]:
    threshold = serialize_datetime(now or datetime.now())
    with _lock:
        rows = _table.search(
            (_query.status == "scheduled")
            & (_query.publish_at.exists())
            & (_query.publish_at <= threshold)
        )

    result = []
    for row in sorted(rows, key=lambda item: item.get("publish_at") or ""):
        result.append({"doc_id": row.doc_id, **dict(row)})
    return result


def remove_scheduled_post(doc_id: int) -> None:
    with _lock:
        _table.remove(doc_ids=[doc_id])
