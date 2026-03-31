"""Файловая статистика и аналитика по работе ботов."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

LOG_DIR = Path("analytics")
EVENTS_LOG_PATH = LOG_DIR / "bot_events.jsonl"
SUMMARY_LOG_PATH = LOG_DIR / "bot_stats_summary.txt"

_LOG_LOCK = Lock()


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    event_type: str,
    *,
    bot: str,
    user_id: int | None = None,
    chat_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Записывает одно событие в JSONL-файл аналитики."""
    _ensure_log_dir()
    record = {
        "timestamp": _utcnow_iso(),
        "event_type": event_type,
        "bot": bot,
        "user_id": user_id,
        "chat_id": chat_id,
        "metadata": metadata or {},
    }
    with _LOG_LOCK:
        with EVENTS_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_command_usage(bot: str, command: str, message) -> None:
    log_event(
        "command_used",
        bot=bot,
        user_id=getattr(getattr(message, "from_user", None), "id", None),
        chat_id=getattr(message, "chat", None).id if getattr(message, "chat", None) else None,
        metadata={"command": command},
    )


def _safe_read_events() -> list[dict]:
    _ensure_log_dir()
    if not EVENTS_LOG_PATH.exists():
        return []

    events: list[dict] = []
    with EVENTS_LOG_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def summarize_events() -> dict:
    events = _safe_read_events()

    by_bot = Counter()
    by_event = Counter()
    commands_by_bot: dict[str, Counter] = defaultdict(Counter)
    top_users_by_bot: dict[str, Counter] = defaultdict(Counter)
    unique_users_by_bot: dict[str, set[int]] = defaultdict(set)
    packs_by_name: dict[str, dict[str, int]] = defaultdict(lambda: {"purchases": 0, "spent": 0})
    card_drops = Counter()
    rarity_drops = Counter()
    bank_stats = {"transfers": 0, "volume": 0}
    battle_stats: dict[str, Counter] = defaultdict(Counter)
    post_stats = Counter()
    reward_stats = {"grants": 0, "total": 0}
    birthday_stats = Counter()
    ai_stats = Counter()

    for event in events:
        bot_name = str(event.get("bot") or "unknown")
        event_type = str(event.get("event_type") or "unknown")
        user_id = event.get("user_id")
        metadata = event.get("metadata") or {}

        by_bot[bot_name] += 1
        by_event[event_type] += 1
        if isinstance(user_id, int):
            unique_users_by_bot[bot_name].add(user_id)
            top_users_by_bot[bot_name][str(user_id)] += 1

        if event_type == "command_used":
            commands_by_bot[bot_name][str(metadata.get("command") or "unknown")] += 1

        if event_type == "pack_purchased":
            pack_name = str(metadata.get("pack_name") or "unknown")
            packs_by_name[pack_name]["purchases"] += 1
            packs_by_name[pack_name]["spent"] += int(metadata.get("price") or 0)

        if event_type == "card_dropped":
            card_name = str(metadata.get("card_name") or "unknown")
            card_drops[card_name] += 1
            rarity_drops[str(metadata.get("rarity") or "unknown")] += 1

        if event_type == "bank_transfer_completed":
            bank_stats["transfers"] += 1
            bank_stats["volume"] += int(metadata.get("amount") or 0)

        if event_type in {"battle_started", "battle_finished"}:
            mode = str(metadata.get("mode") or "unknown")
            battle_stats[mode][event_type] += 1
            if event_type == "battle_finished":
                battle_stats[mode][f"winner:{metadata.get('winner_name') or metadata.get('winner_user_id') or 'unknown'}"] += 1

        if event_type.startswith(("post_", "question_", "album_")):
            post_stats[event_type] += 1

        if event_type == "event_reward_granted":
            reward_stats["grants"] += 1
            reward_stats["total"] += int(metadata.get("reward") or 0)

        if event_type.startswith("birthday_"):
            birthday_stats[event_type] += int(metadata.get("count") or 1)

        if event_type.startswith("ai_"):
            ai_stats[event_type] += 1

    return {
        "generated_at": _utcnow_iso(),
        "total_events": len(events),
        "events_by_bot": dict(by_bot),
        "events_by_type": dict(by_event),
        "unique_users_by_bot": {bot: len(users) for bot, users in unique_users_by_bot.items()},
        "top_users_by_bot": {bot: dict(counter) for bot, counter in top_users_by_bot.items()},
        "commands_by_bot": {bot: dict(counter) for bot, counter in commands_by_bot.items()},
        "packs": dict(packs_by_name),
        "card_drops": dict(card_drops.most_common()),
        "rarity_drops": dict(rarity_drops),
        "bank": bank_stats,
        "battles": {mode: dict(counter) for mode, counter in battle_stats.items()},
        "posts": dict(post_stats),
        "rewards": reward_stats,
        "birthdays": dict(birthday_stats),
        "ai": dict(ai_stats),
    }


def _top_lines(counter_mapping: dict[str, int], title: str, limit: int = 10) -> list[str]:
    if not counter_mapping:
        return [f"{title}: нет данных"]
    lines = [title]
    for index, (name, count) in enumerate(sorted(counter_mapping.items(), key=lambda item: (-item[1], item[0]))[:limit], start=1):
        lines.append(f"{index}. {name} — {count}")
    return lines


def build_summary_text(summary: dict) -> str:
    lines = [
        "=== Сводка аналитики бота ===",
        f"Сгенерировано: {summary['generated_at']}",
        f"Всего событий: {summary['total_events']}",
        "",
    ]
    lines.extend(_top_lines(summary["events_by_bot"], "Активность по ботам"))
    lines.append("")
    lines.extend(_top_lines(summary["events_by_type"], "События по типам"))
    lines.append("")

    if summary["unique_users_by_bot"]:
        lines.append("Уникальные пользователи по ботам:")
        for bot_name, users_count in sorted(summary["unique_users_by_bot"].items()):
            lines.append(f"- {bot_name}: {users_count}")
        lines.append("")

    for bot_name, commands in summary["commands_by_bot"].items():
        lines.extend(_top_lines(commands, f"Команды бота {bot_name}", limit=15))
        lines.append("")

    for bot_name, users in summary["top_users_by_bot"].items():
        lines.extend(_top_lines(users, f"Самые активные user_id в боте {bot_name}", limit=10))
        lines.append("")

    if summary["packs"]:
        lines.append("Покупки паков:")
        for pack_name, pack_data in sorted(summary["packs"].items(), key=lambda item: (-item[1]["purchases"], item[0])):
            lines.append(f"- {pack_name}: покупок {pack_data['purchases']}, потрачено {pack_data['spent']} IB")
        lines.append("")

    lines.extend(_top_lines(summary["card_drops"], "Частота выпадения карт", limit=20))
    lines.append("")
    lines.extend(_top_lines(summary["rarity_drops"], "Частота выпадения по редкости", limit=10))
    lines.append("")
    lines.append(f"Банк: переводов {summary['bank']['transfers']}, объём {summary['bank']['volume']} IB")
    lines.append("")

    if summary["battles"]:
        lines.append("Бои:")
        for mode, battle_data in summary["battles"].items():
            lines.append(f"- {mode}: стартов {battle_data.get('battle_started', 0)}, завершений {battle_data.get('battle_finished', 0)}")
        lines.append("")

    if summary["rewards"]["grants"]:
        lines.append(
            f"Карточные ивенты: выдано наград {summary['rewards']['grants']}, суммарно {summary['rewards']['total']} IB"
        )
        lines.append("")

    if summary["posts"]:
        lines.append("Предложка:")
        for event_type, count in sorted(summary["posts"].items()):
            lines.append(f"- {event_type}: {count}")
        lines.append("")

    if summary["birthdays"]:
        lines.append("Дни рождения:")
        for event_type, count in sorted(summary["birthdays"].items()):
            lines.append(f"- {event_type}: {count}")
        lines.append("")

    if summary["ai"]:
        lines.append("AI:")
        for event_type, count in sorted(summary["ai"].items()):
            lines.append(f"- {event_type}: {count}")

    return "\n".join(lines).strip() + "\n"


def write_summary_report() -> Path:
    """Пересобирает текстовую сводку статистики и возвращает путь к ней."""
    _ensure_log_dir()
    summary = summarize_events()
    summary_text = build_summary_text(summary)
    with _LOG_LOCK:
        SUMMARY_LOG_PATH.write_text(summary_text, encoding="utf-8")
    return SUMMARY_LOG_PATH
