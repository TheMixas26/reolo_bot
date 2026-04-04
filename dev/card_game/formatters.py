"""Форматирование текста карточной игры."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

from card_game.catalog import get_pack_name, get_rarity_label
from settings import CURRENCY_NAME_GENITIVE, CURRENCY_SHORT_NAME

if TYPE_CHECKING:
    from handlers.card_handlers.state import ChallengeLobby


def format_card_name(card: dict) -> str:
    return escape(str(card.get("name", "Неизвестная карта")))


def format_user_name(name: str) -> str:
    return escape(name or "Игрок")


def format_card_stats(card: dict) -> str:
    return f"❤️{card.get('hp', 0)} ⚔️{card.get('atk', 0)} 🛡️{card.get('def', 0)}"


def format_card_line(card: dict, *, include_amount: bool = False) -> str:
    amount = f" x{card.get('amount', 1)}" if include_amount else ""
    rarity = get_rarity_label(card.get("rarity"))
    pack_name = get_pack_name(card)
    return f"{format_card_name(card)}{amount} ({rarity}) — {format_card_stats(card)} | пак: {escape(pack_name)}"


def format_inventory(cards: list[dict]) -> str:
    lines = ["🎒 <b>Ваш инвентарь:</b>"]
    lines.extend(f"• {format_card_line(card, include_amount=True)}" for card in cards)
    return "\n".join(lines)


def format_card_catalog(cards: list[dict]) -> str:
    lines = ["📖 <b>Все доступные карты:</b>"]
    lines.extend(f"{card['id']}. {format_card_line(card)}" for card in cards)
    return "\n".join(lines)


def format_pack_menu(packs: list[dict], balance: int) -> str:
    lines = [
        "🎁 <b>Выберите пак для открытия</b>",
        "",
        f"Ваш баланс: <b>{balance}</b> {CURRENCY_NAME_GENITIVE}",
        "В каждом паке лежат 3 карты только из своей категории.",
    ]
    for pack in packs:
        description = f" — {escape(pack['description'])}" if pack.get("description") else ""
        lines.append(f"• {escape(pack['name'])} | {pack['price']} {CURRENCY_SHORT_NAME}{description}")
    return "\n".join(lines)


def format_pack_animation_frame(pack_name: str, step: int, total_steps: int) -> str:
    filled = "■" * step
    empty = "□" * max(0, total_steps - step)
    phrases = {
        1: "Пак ложится на стол...",
        2: "Фольга трещит и раскрывается...",
        3: "Карты уже мелькают в свете...",
        4: "Последний рывок...",
    }
    phrase = phrases.get(step, "Открываем пак...")
    return f"🎁 <b>{escape(pack_name)}</b>\n{phrase}\n\n{filled}{empty}"


def format_pack_result(pack_name: str, cards: list[dict], balance: int | None = None) -> str:
    lines = [f"✨ <b>Пак «{escape(pack_name)}» открыт!</b>"]
    if balance is not None:
        lines.append(f"Остаток: <b>{balance}</b> {CURRENCY_NAME_GENITIVE}")
    lines.append("")
    lines.extend(f"• {format_card_line(card)}" for card in cards)
    return "\n".join(lines)


def format_wallet(balance: int) -> str:
    return f"💰 Ваш карточный бюджет: <b>{balance}</b> {CURRENCY_NAME_GENITIVE}"


def format_event_list(events: list[dict]) -> str:
    if not events:
        return "Сейчас активных карточных ивентов нет."

    lines = ["🏛 <b>Активные карточные ивенты:</b>", ""]
    for event in events:
        description = f"\n{escape(event['description'])}" if event.get("description") else ""
        lines.append(f"#{event['id']} {escape(event['title'])} — награда {event['reward']} {CURRENCY_SHORT_NAME}{description}")
        lines.append("")
    return "\n".join(lines).strip()


def format_admin_event_list(events: list[dict]) -> str:
    if not events:
        return "Карточных ивентов пока нет."

    lines = ["Ивенты карточной игры:"]
    for event in events:
        lines.append(f"#{event['id']} [{event['status']}] {event['title']} — {event['reward']} {CURRENCY_SHORT_NAME}")
    return "\n".join(lines)


def format_admin_pack_list(packs: list[dict]) -> str:
    if not packs:
        return "Паков пока нет."

    lines = ["Паки карточной игры:"]
    for pack in packs:
        status = "активен" if pack["is_active"] else "скрыт"
        lines.append(f"#{pack['id']} {pack['name']} — {pack['price']} {CURRENCY_SHORT_NAME} ({status})")
    return "\n".join(lines)


def format_invite(lobby: "ChallengeLobby") -> str:
    mode_title = "дуэль" if lobby.mode == "duel" else "командный бой"
    return (
        f"⚔️ <b>Вызов на {mode_title}</b>\n\n"
        f"{format_user_name(lobby.initiator_name)} вызывает {format_user_name(lobby.opponent_name)}.\n"
        f"Подтвердите участие, чтобы перейти к выбору карт."
    )


def format_selection_prompt(lobby: "ChallengeLobby", team_size: int) -> str:
    selector_id = lobby.current_selector_id()
    if selector_id is None:
        return "Ожидание выбора."

    selected_cards = lobby.get_selection(selector_id)
    selected_names = ", ".join(format_card_name(card) for card in selected_cards) if selected_cards else "ничего"
    target_count = 1 if lobby.mode == "duel" else team_size
    return (
        f"🃏 <b>Выбор карт</b>\n\n"
        f"Сейчас выбирает: {format_user_name(lobby.current_selector_name() or '')}\n"
        f"Нужно карт: {target_count}\n"
        f"Уже выбрано: {len(selected_cards)}\n"
        f"Текущий выбор: {selected_names}"
    )


def format_lobby_ready(lobby: "ChallengeLobby") -> str:
    title = "Дуэль" if lobby.mode == "duel" else "Командный бой"
    left = ", ".join(str(card.get("name", "?")) for card in lobby.initiator_selection)
    right = ", ".join(str(card.get("name", "?")) for card in lobby.opponent_selection)
    return (
        f"⚔️ {title} начинается\n\n"
        f"{lobby.initiator_name}: {left}\n"
        f"{lobby.opponent_name}: {right}"
    )
