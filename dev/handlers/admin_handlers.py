from config import predlojka_bot, admin
from database.scheduled_posts_db import list_scheduled_posts
from analytics.stats import log_command_usage
from posting.runtime import predlojka_telegram_adapter
import logging

logger = logging.getLogger(__name__)



def _preview_scheduled_payload(payload: dict, content_type: str) -> str:
    if content_type == "album":
        media = payload.get("media") or []
        first_caption = ""
        if media:
            first_caption = (media[0].get("caption") or "").strip()
        snippet = first_caption or f"Альбом из {len(media)} элементов"
    else:
        snippet = (payload.get("publish_text") or "").strip()

    snippet = snippet.replace("\n", " ")
    if len(snippet) > 90:
        snippet = snippet[:87] + "..."
    return snippet or "(без текста)"


@predlojka_bot.message_handler(commands=['drafts', 'scheduled_posts'])
def show_scheduled_posts(message):
    if message.from_user.id != admin:
        return

    log_command_usage("predlojka", "scheduled_posts", message)
    rows = list_scheduled_posts(limit=30)

    if not rows:
        predlojka_telegram_adapter.reply_to(message, "В `scheduled_posts` пока пусто: ни черновиков, ни отложек нет.", parse_mode="Markdown")
        return

    lines = ["Содержимое `scheduled_posts`:\n"]
    for row in rows:
        status_label = "Запланировано" if row["status"] == "scheduled" else "Черновик"
        publish_at = row.get("publish_at") or "без даты"
        content_type = row.get("content_type") or "unknown"
        source_user_id = row.get("source_user_id")
        preview = _preview_scheduled_payload(row.get("payload") or {}, content_type)
        lines.append(
            f"#{row['doc_id']} | {status_label} | {content_type} | {publish_at} | user {source_user_id}\n{preview}\n"
        )

    predlojka_telegram_adapter.reply_to(message, "\n".join(lines), parse_mode="Markdown")

