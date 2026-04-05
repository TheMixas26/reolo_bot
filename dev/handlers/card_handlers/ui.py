"""Telegram-представление карточной игры."""

from __future__ import annotations

from config import rpg_bot
from database.sqlite_db import get_balance, get_inventory
from posting.runtime import rpg_telegram_adapter

from card_game.formatters import (
    format_invite,
    format_lobby_ready,
    format_pack_menu,
    format_selection_prompt,
)
from card_game.services import TEAM_SIZE
from handlers.card_handlers.keyboards import (
    build_duel_action_keyboard,
    build_duel_selection_keyboard,
    build_invite_keyboard,
    build_pack_keyboard,
    build_team_action_keyboard,
    build_team_actor_keyboard,
    build_team_selection_keyboard,
    build_team_target_keyboard,
)


def send_pack_menu(chat_id: int, user_id: int, packs: list[dict]):
    balance = int(get_balance(user_id))
    return rpg_telegram_adapter.send_message(chat_id, format_pack_menu(packs, balance), parse_mode="HTML", reply_markup=build_pack_keyboard(packs))


def show_lobby_invite(lobby) -> None:
    rpg_telegram_adapter.edit_message_text(
        format_invite(lobby),
        chat_id=lobby.chat_id,
        message_id=lobby.message_id,
        parse_mode="HTML",
        reply_markup=build_invite_keyboard(),
    )


def show_lobby_selection(lobby) -> None:
    selector_id = lobby.current_selector_id()
    if selector_id is None:
        return

    inventory = get_inventory(selector_id)
    if lobby.mode == "duel":
        keyboard = build_duel_selection_keyboard(inventory)
    else:
        selected_cards = lobby.get_selection(selector_id)
        selected_counts: dict[int, int] = {}
        for card in selected_cards:
            card_id = int(card["id"])
            selected_counts[card_id] = selected_counts.get(card_id, 0) + 1
        keyboard = build_team_selection_keyboard(
            inventory,
            selected_counts,
            can_ready=len(selected_cards) == TEAM_SIZE,
        )

    rpg_telegram_adapter.edit_message_text(
        format_selection_prompt(lobby, TEAM_SIZE),
        chat_id=lobby.chat_id,
        message_id=lobby.message_id,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


def show_lobby_started(lobby, session) -> None:
    rpg_telegram_adapter.edit_message_text(
        f"{format_lobby_ready(lobby)}\n\n{session.get_state()}",
        chat_id=lobby.chat_id,
        message_id=lobby.message_id,
        reply_markup=get_battle_keyboard(session),
    )


def update_battle_message(chat_id: int, message_id: int, session, extra_text: str | None = None) -> None:
    text = session.get_state()
    if extra_text:
        text = f"{extra_text}\n\n{text}"
    reply_markup = None if session.finished else get_battle_keyboard(session)
    rpg_telegram_adapter.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=reply_markup,
    )


def get_battle_keyboard(session):
    if session.mode == "duel":
        return build_duel_action_keyboard()
    if session.stage == "choose_actor":
        return build_team_actor_keyboard(session.get_selectable_actors(session.current_turn_user_id))
    if session.stage == "choose_action":
        return build_team_action_keyboard()
    return build_team_target_keyboard(session.get_selectable_targets(session.current_turn_user_id))
