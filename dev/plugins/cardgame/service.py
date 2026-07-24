from __future__ import annotations
from aiogram import types
from .catalog import get_rarity_label, get_pack_name, RARITY_WEIGHTS
from core.core_plugin.stats import log_event
from dataclasses import dataclass, field
from html import escape
import random
from settings import CURRENCY_NAME_GENITIVE, CURRENCY_SHORT_NAME
from plugins.bank.db import get_balance, set_balance
from database.sqlite_db import create_user_if_missing

TEAM_SIZE = 5
PACK_SIZE = 3

from .db import (
    get_pack_names, get_cards_by_category,
    get_inventory, get_pack_by_id,
    add_to_inventory,
)

MessageKey = tuple[int, int]
_pack_flows: dict[MessageKey, PackFlow] = {}
_lobbies: dict[MessageKey, ChallengeLobby] = {}
_user_lobbies: dict[int, MessageKey] = {}

from plugins.cardgame.battle import DuelSession, TeamBattleSession

GameSession = DuelSession | TeamBattleSession
_active_sessions: dict[int, GameSession] = {}


def start_duel(
    player1_id: int,
    player1_name: str,
    player1_card: dict,
    player2_id: int,
    player2_name: str,
    player2_card: dict,
) -> DuelSession:
    session = DuelSession(player1_id, player1_name, player1_card, player2_id, player2_name, player2_card)
    for user_id in session.get_participant_ids():
        _active_sessions[user_id] = session
    return session


def start_team_battle(
    player1_id: int,
    player1_name: str,
    team1_cards: list[dict],
    player2_id: int,
    player2_name: str,
    team2_cards: list[dict],
) -> TeamBattleSession:
    session = TeamBattleSession(player1_id, player1_name, team1_cards, player2_id, player2_name, team2_cards)
    for user_id in session.get_participant_ids():
        _active_sessions[user_id] = session
    return session


def get_session(user_id: int) -> GameSession | None:
    return _active_sessions.get(user_id)


def end_session(user_id: int) -> None:
    session = _active_sessions.get(user_id)
    if session is None:
        return
    for participant_id in session.get_participant_ids():
        _active_sessions.pop(participant_id, None)




def _selection_limit(lobby) -> int:
        return 1 if lobby.mode == "duel" else TEAM_SIZE


def _find_card_in_inventory(user_id: int, card_id: int) -> dict | None:
    inventory = get_inventory(user_id)
    return next((card for card in inventory if int(card["id"]) == card_id), None)


def _log_battle_started(session, chat_id: int) -> None:
    log_event(
        "battle_started",
        bot="rpg",
        chat_id=chat_id,
        metadata={
            "mode": session.mode,
            "participants": [
                {"user_id": side.user_id, "name": side.name}
                for side in session.sides.values()
            ],
        },
    )


def _log_battle_finished(session, *, chat_id: int, trigger_user_id: int) -> None:
    winner_id = session.winner_user_id
    winner_name = session.sides[winner_id].name if winner_id in session.sides else None
    log_event(
        "battle_finished",
        bot="rpg",
        user_id=trigger_user_id,
        chat_id=chat_id,
        metadata={"mode": session.mode, "winner_user_id": winner_id, "winner_name": winner_name},
    )


def build_pack_keyboard(packs: list[dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    for pack in packs:
        markup.add(types.InlineKeyboardButton(f"{pack['name']} — {pack['price']} IB", callback_data=f"cg_pack:{pack['id']}"))
    markup.add(types.InlineKeyboardButton("Закрыть", callback_data="cg_pack_cancel"))
    return markup


def build_invite_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Принять", callback_data="cg_invite_accept"),
        types.InlineKeyboardButton("Отклонить", callback_data="cg_invite_decline"),
    )
    markup.add(types.InlineKeyboardButton("Отменить вызов", callback_data="cg_invite_cancel"))
    return markup


def build_duel_selection_keyboard(cards: list[dict]) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    for card in cards:
        markup.add(
            types.InlineKeyboardButton(
                f"{card['name']} ({get_rarity_label(card['rarity'])})",
                callback_data=f"cg_pick:{card['id']}",
            )
        )
    markup.add(types.InlineKeyboardButton("Отменить вызов", callback_data="cg_invite_cancel"))
    return markup


def build_team_selection_keyboard(cards: list[dict], selected_counts: dict[int, int], *, can_ready: bool) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    for card in cards:
        owned_amount = int(card.get("amount", 1))
        selected_amount = selected_counts.get(int(card["id"]), 0)
        remaining_amount = owned_amount - selected_amount
        if remaining_amount <= 0:
            continue
        markup.add(
            types.InlineKeyboardButton(
                f"{card['name']} ({get_rarity_label(card['rarity'])}) x{remaining_amount}",
                callback_data=f"cg_pick:{card['id']}",
            )
        )
    ready_callback = "cg_pick_ready" if can_ready else "cg_pick_wait"
    markup.row(
        types.InlineKeyboardButton("Сбросить выбор", callback_data="cg_pick_reset"),
        types.InlineKeyboardButton("Готово", callback_data=ready_callback),
    )
    markup.add(types.InlineKeyboardButton("Отменить вызов", callback_data="cg_invite_cancel"))
    return markup


def build_duel_action_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Атаковать", callback_data="cg_duel_action:attack"),
        types.InlineKeyboardButton("Защищаться", callback_data="cg_duel_action:defend"),
    )
    markup.add(types.InlineKeyboardButton("Отменить бой", callback_data="cg_battle_cancel"))
    return markup


def build_team_actor_keyboard(cards) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    for card in cards:
        markup.add(types.InlineKeyboardButton(card.name, callback_data=f"cg_team_actor:{card.instance_id}"))
    markup.add(types.InlineKeyboardButton("Отменить бой", callback_data="cg_battle_cancel"))
    return markup


def build_team_action_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Атаковать", callback_data="cg_team_action:attack"),
        types.InlineKeyboardButton("Защищаться", callback_data="cg_team_action:defend"),
    )
    markup.row(
        types.InlineKeyboardButton("Выбрать другую карту", callback_data="cg_team_action:back"),
        types.InlineKeyboardButton("Отменить бой", callback_data="cg_battle_cancel"),
    )
    return markup


def build_team_target_keyboard(cards) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    for card in cards:
        markup.add(types.InlineKeyboardButton(card.name, callback_data=f"cg_team_target:{card.instance_id}"))
    markup.row(
        types.InlineKeyboardButton("Назад", callback_data="cg_team_action:back"),
        types.InlineKeyboardButton("Отменить бой", callback_data="cg_battle_cancel"),
    )
    return markup

@dataclass
class PackFlow:
    owner_id: int
    chat_id: int
    message_id: int
    packs: list[dict]


@dataclass
class ChallengeLobby:
    mode: str
    chat_id: int
    message_id: int
    initiator_id: int
    initiator_name: str
    opponent_id: int
    opponent_name: str
    stage: str = "invite"
    initiator_selection: list[dict] = field(default_factory=list)
    opponent_selection: list[dict] = field(default_factory=list)

    def participant_ids(self) -> tuple[int, int]:
        return (self.initiator_id, self.opponent_id)

    def current_selector_id(self) -> int | None:
        if self.stage == "initiator_pick":
            return self.initiator_id
        if self.stage == "opponent_pick":
            return self.opponent_id
        return None

    def current_selector_name(self) -> str | None:
        if self.stage == "initiator_pick":
            return self.initiator_name
        if self.stage == "opponent_pick":
            return self.opponent_name
        return None

    def get_selection(self, user_id: int) -> list[dict]:
        if user_id == self.initiator_id:
            return self.initiator_selection
        return self.opponent_selection

    def reset_selection(self, user_id: int) -> None:
        if user_id == self.initiator_id:
            self.initiator_selection = []
        else:
            self.opponent_selection = []

def build_message_key(chat_id: int, message_id: int) -> MessageKey:
    return (chat_id, message_id)


def register_pack_flow(flow: PackFlow) -> None:
    _pack_flows[build_message_key(flow.chat_id, flow.message_id)] = flow


def get_pack_flow(chat_id: int, message_id: int) -> PackFlow | None:
    return _pack_flows.get(build_message_key(chat_id, message_id))


def clear_pack_flow(chat_id: int, message_id: int) -> None:
    _pack_flows.pop(build_message_key(chat_id, message_id), None)


def register_lobby(lobby: ChallengeLobby) -> None:
    key = build_message_key(lobby.chat_id, lobby.message_id)
    _lobbies[key] = lobby
    for user_id in lobby.participant_ids():
        _user_lobbies[user_id] = key


def get_lobby(chat_id: int, message_id: int) -> ChallengeLobby | None:
    return _lobbies.get(build_message_key(chat_id, message_id))


def get_lobby_by_user(user_id: int) -> ChallengeLobby | None:
    key = _user_lobbies.get(user_id)
    if key is None:
        return None
    return _lobbies.get(key)


def clear_lobby(chat_id: int, message_id: int) -> None:
    key = build_message_key(chat_id, message_id)
    lobby = _lobbies.pop(key, None)
    if lobby is None:
        return
    for user_id in lobby.participant_ids():
        _user_lobbies.pop(user_id, None)


def clear_lobby_by_user(user_id: int) -> None:
    key = _user_lobbies.get(user_id)
    if key is None:
        return
    clear_lobby(*key)


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

def _display_name(user) -> str:
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}".strip()
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return f"id{user.id}"


def _reply_target(message):
    reply = getattr(message, "reply_to_message", None)
    if reply is None or reply.from_user is None:
        return None
    if reply.from_user.id == message.from_user.id:
        return None
    return reply.from_user



def _user_busy(user_id: int) -> bool:
    return get_session(user_id) is not None or get_lobby_by_user(user_id) is not None


def _ensure_user(message) -> None:
    create_user_if_missing(message.from_user.id, message.from_user.first_name, message.from_user.last_name)


def _none_if_dash(value: str) -> str | None:
    return None if value.strip() in {"-", ""} else value.strip()


def _parse_card_fields(parts: list[str]) -> dict:
    if len(parts) < 7:
        raise ValueError("Недостаточно параметров карты.")

    return {
        "name": parts[0].strip(),
        "rarity": parts[1].strip(),
        "hp": int(parts[2].strip()),
        "atk": int(parts[3].strip()),
        "def": int(parts[4].strip()),
        "type": _none_if_dash(parts[5]),
        "category": parts[6].strip(),
        "ability": _none_if_dash(parts[7]) if len(parts) > 7 else None,
        "image": _none_if_dash(parts[8]) if len(parts) > 8 else None,
        "desc": _none_if_dash(parts[9]) if len(parts) > 9 else None,
    }


def _parse_update_fields(parts: list[str]) -> dict:
    updates: dict = {}
    for part in parts:
        key, value = [item.strip() for item in part.split("=", 1)]
        if key in {"hp", "atk", "def"}:
            updates[key] = int(value)
        elif key == "is_active":
            updates[key] = value.lower() in {"1", "true", "yes", "on", "active", "активен"}
        else:
            updates[key] = _none_if_dash(value)
    return updates


def roll_card(user_id: int, pack_name: str | None = None):
    selected_pack = pack_name or next(iter(list_packs()), None)
    if selected_pack is None:
        raise ValueError("Нет доступных паков для открытия.")
    return open_pack(user_id, selected_pack)


def list_packs() -> list[str]:
    return get_pack_names()


def purchase_and_open_pack(user_id: int, pack_id: int, *, pack_size: int = PACK_SIZE) -> tuple[dict, list[dict], int]:
    pack = get_pack_by_id(pack_id)
    if pack is None or not pack.get("is_active"):
        raise ValueError("Пак недоступен.")
    if not get_cards_by_category(pack["name"]):
        raise ValueError("В этом паке пока нет карт. Сначала добавьте их админской командой.")

    balance = int(get_balance(user_id))
    price = int(pack["price"])
    if balance < price:
        raise ValueError(f"Недостаточно средств. Нужно {price}, у вас {balance}.")

    set_balance(user_id, balance - price)
    cards = open_pack(user_id, pack["name"], pack_size=pack_size)
    return pack, cards, balance - price


def open_pack(user_id: int, pack_name: str, *, pack_size: int = PACK_SIZE) -> list[dict]:
    """Открывает конкретный пак и возвращает полученные карты."""
    pack_cards = get_cards_by_category(pack_name)
    if not pack_cards:
        raise ValueError(f"Пак «{pack_name}» не найден.")

    rarities = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    cards: list[dict] = []

    for _ in range(pack_size):
        selected_rarity = random.choices(rarities, weights=weights, k=1)[0]
        selected_label = get_rarity_label(selected_rarity)
        rarity_pool = [card for card in pack_cards if get_rarity_label(card.get("rarity")) == selected_label]
        if not rarity_pool:
            rarity_pool = pack_cards

        card = random.choice(rarity_pool)
        add_to_inventory(user_id, card["id"])
        cards.append(card)

    return cards


def count_total_inventory_cards(cards: list[dict]) -> int:
    return sum(int(card.get("amount", 1)) for card in cards)
