"""Callback-обработчики карточного бота."""

from __future__ import annotations

import time

from analytics.stats import log_event
from config import rpg_bot
from database.sqlite_db import create_user_if_missing, get_inventory
from posting.runtime import rpg_telegram_adapter

from card_game.battle import DuelSession, TeamBattleSession
from card_game.formatters import format_pack_animation_frame, format_pack_result
from card_game.services import TEAM_SIZE, purchase_and_open_pack
from card_game.sessions import end_session, get_session, start_duel, start_team_battle
from handlers.card_handlers.state import (
    clear_lobby,
    clear_pack_flow,
    get_lobby,
    get_pack_flow,
)
from handlers.card_handlers.ui import show_lobby_selection, show_lobby_started, update_battle_message


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


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_pack_cancel")
def cancel_pack_selection(call):
    flow = get_pack_flow(call.message.chat.id, call.message.message_id)
    if flow is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Это окно паков уже неактивно.")
        return
    if call.from_user.id != flow.owner_id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот пак выбирает другой игрок.")
        return

    clear_pack_flow(call.message.chat.id, call.message.message_id)
    log_event("pack_selection_cancelled", bot="rpg", user_id=call.from_user.id, chat_id=call.message.chat.id)
    rpg_telegram_adapter.edit_message_text("Открытие пака отменено.", chat_id=call.message.chat.id, message_id=call.message.message_id)


@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith("cg_pack:"))
def open_selected_pack(call):
    flow = get_pack_flow(call.message.chat.id, call.message.message_id)
    if flow is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Это окно паков уже неактивно.")
        return
    if call.from_user.id != flow.owner_id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот пак выбирает другой игрок.")
        return

    pack_id = int(call.data.split(":", 1)[1])
    pack = next((item for item in flow.packs if int(item["id"]) == pack_id), None)
    if pack is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Такого пака здесь нет.")
        return

    create_user_if_missing(call.from_user.id, call.from_user.first_name, call.from_user.last_name)
    pack_name = pack["name"]
    for step in range(1, 5):
        rpg_telegram_adapter.edit_message_text(
            format_pack_animation_frame(pack_name, step, 4),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )
        time.sleep(0.45)

    try:
        _, cards, balance_after = purchase_and_open_pack(call.from_user.id, pack_id)
    except ValueError as error:
        clear_pack_flow(call.message.chat.id, call.message.message_id)
        rpg_telegram_adapter.edit_message_text(str(error), chat_id=call.message.chat.id, message_id=call.message.message_id)
        return

    log_event(
        "pack_purchased",
        bot="rpg",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"pack_id": pack_id, "pack_name": pack_name, "price": int(pack["price"]), "cards_count": len(cards), "balance_after": balance_after},
    )
    for card in cards:
        log_event(
            "card_dropped",
            bot="rpg",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={"pack_id": pack_id, "pack_name": pack_name, "card_id": card["id"], "card_name": card["name"], "rarity": card.get("rarity")},
        )

    for reveal_count in range(1, len(cards) + 1):
        rpg_telegram_adapter.edit_message_text(
            format_pack_result(pack_name, cards[:reveal_count], balance_after),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )
        time.sleep(0.35)

    clear_pack_flow(call.message.chat.id, call.message.message_id)


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_invite_accept")
def accept_invite(call):
    lobby = get_lobby(call.message.chat.id, call.message.message_id)
    if lobby is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот вызов уже неактивен.")
        return
    if call.from_user.id != lobby.opponent_id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Принять вызов может только приглашённый игрок.")
        return

    lobby.stage = "initiator_pick"
    log_event(
        "battle_challenge_accepted",
        bot="rpg",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"mode": lobby.mode, "initiator_id": lobby.initiator_id, "opponent_id": lobby.opponent_id},
    )
    show_lobby_selection(lobby)


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_invite_decline")
def decline_invite(call):
    lobby = get_lobby(call.message.chat.id, call.message.message_id)
    if lobby is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот вызов уже неактивен.")
        return
    if call.from_user.id != lobby.opponent_id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Отклонить вызов может только приглашённый игрок.")
        return

    clear_lobby(call.message.chat.id, call.message.message_id)
    log_event(
        "battle_challenge_declined",
        bot="rpg",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"mode": lobby.mode, "initiator_id": lobby.initiator_id, "opponent_id": lobby.opponent_id},
    )
    rpg_telegram_adapter.edit_message_text(
        "Вызов отклонён.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
    )


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_invite_cancel")
def cancel_invite(call):
    lobby = get_lobby(call.message.chat.id, call.message.message_id)
    if lobby is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот вызов уже неактивен.")
        return
    if call.from_user.id not in lobby.participant_ids():
        rpg_telegram_adapter.answer_callback_query(call.id, "Вы не участник этого вызова.")
        return

    clear_lobby(call.message.chat.id, call.message.message_id)
    log_event(
        "battle_challenge_cancelled",
        bot="rpg",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"mode": lobby.mode, "initiator_id": lobby.initiator_id, "opponent_id": lobby.opponent_id},
    )
    rpg_telegram_adapter.edit_message_text(
        "Вызов отменён.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
    )


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_pick_wait")
def wait_for_full_team(call):
    rpg_telegram_adapter.answer_callback_query(call.id, f"Сначала нужно выбрать ровно {TEAM_SIZE} карт.")


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_pick_reset")
def reset_selection(call):
    lobby = get_lobby(call.message.chat.id, call.message.message_id)
    if lobby is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот вызов уже неактивен.")
        return

    selector_id = lobby.current_selector_id()
    if selector_id != call.from_user.id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Сейчас выбор делает другой игрок.")
        return

    lobby.reset_selection(call.from_user.id)
    show_lobby_selection(lobby)


@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith("cg_pick:"))
def pick_card(call):
    lobby = get_lobby(call.message.chat.id, call.message.message_id)
    if lobby is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот вызов уже неактивен.")
        return

    selector_id = lobby.current_selector_id()
    if selector_id != call.from_user.id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Сейчас выбор делает другой игрок.")
        return

    card_id = int(call.data.split(":", 1)[1])
    card = _find_card_in_inventory(call.from_user.id, card_id)
    if card is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этой карты нет в вашем инвентаре.")
        return

    selected_cards = lobby.get_selection(call.from_user.id)
    if lobby.mode == "team":
        selected_count = sum(1 for item in selected_cards if int(item["id"]) == card_id)
        if selected_count >= int(card.get("amount", 1)):
            rpg_telegram_adapter.answer_callback_query(call.id, "У вас больше нет свободных копий этой карты.")
            return

    if len(selected_cards) >= _selection_limit(lobby):
        rpg_telegram_adapter.answer_callback_query(call.id, "Лимит выбора уже достигнут.")
        return

    selected_cards.append(dict(card))
    if lobby.mode == "duel":
        if call.from_user.id == lobby.initiator_id:
            lobby.stage = "opponent_pick"
            show_lobby_selection(lobby)
            return

        session = start_duel(
            lobby.initiator_id,
            lobby.initiator_name,
            lobby.initiator_selection[0],
            lobby.opponent_id,
            lobby.opponent_name,
            lobby.opponent_selection[0],
        )
        show_lobby_started(lobby, session)
        _log_battle_started(session, call.message.chat.id)
        clear_lobby(call.message.chat.id, call.message.message_id)
        return

    show_lobby_selection(lobby)


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_pick_ready")
def confirm_pick(call):
    lobby = get_lobby(call.message.chat.id, call.message.message_id)
    if lobby is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Этот вызов уже неактивен.")
        return

    selector_id = lobby.current_selector_id()
    if selector_id != call.from_user.id:
        rpg_telegram_adapter.answer_callback_query(call.id, "Сейчас выбор делает другой игрок.")
        return
    if lobby.mode != "team":
        rpg_telegram_adapter.answer_callback_query(call.id, "Для дуэли достаточно выбрать одну карту.")
        return

    selected_cards = lobby.get_selection(call.from_user.id)
    if len(selected_cards) != TEAM_SIZE:
        rpg_telegram_adapter.answer_callback_query(call.id, f"Нужно выбрать ровно {TEAM_SIZE} карт.")
        return

    if call.from_user.id == lobby.initiator_id:
        lobby.stage = "opponent_pick"
        show_lobby_selection(lobby)
        return

    session = start_team_battle(
        lobby.initiator_id,
        lobby.initiator_name,
        lobby.initiator_selection,
        lobby.opponent_id,
        lobby.opponent_name,
        lobby.opponent_selection,
    )
    show_lobby_started(lobby, session)
    _log_battle_started(session, call.message.chat.id)
    clear_lobby(call.message.chat.id, call.message.message_id)


@rpg_bot.callback_query_handler(func=lambda call: call.data == "cg_battle_cancel")
def cancel_battle(call):
    session = get_session(call.from_user.id)
    if session is None:
        rpg_telegram_adapter.answer_callback_query(call.id, "Активного боя уже нет.")
        return

    log_event(
        "battle_cancelled",
        bot="rpg",
        user_id=call.from_user.id,
        chat_id=call.message.chat.id,
        metadata={"mode": session.mode, "source": "callback"},
    )
    end_session(call.from_user.id)
    rpg_telegram_adapter.edit_message_text("Бой отменён.", chat_id=call.message.chat.id, message_id=call.message.message_id)


@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith("cg_duel_action:"))
def duel_action(call):
    session = get_session(call.from_user.id)
    if not isinstance(session, DuelSession):
        rpg_telegram_adapter.answer_callback_query(call.id, "Активной дуэли нет.")
        return

    action = call.data.split(":", 1)[1]
    if action not in session.get_available_actions(call.from_user.id):
        rpg_telegram_adapter.answer_callback_query(call.id, "Сейчас не ваш ход.")
        return

    finished, text = session.perform_action(call.from_user.id, action)
    if finished:
        _log_battle_finished(session, chat_id=call.message.chat.id, trigger_user_id=call.from_user.id)
        rpg_telegram_adapter.edit_message_text(f"{text}\n\n{session.get_state()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
        end_session(call.from_user.id)
        return

    update_battle_message(call.message.chat.id, call.message.message_id, session, text)


@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith("cg_team_actor:"))
def choose_team_actor(call):
    session = get_session(call.from_user.id)
    if not isinstance(session, TeamBattleSession):
        rpg_telegram_adapter.answer_callback_query(call.id, "Активного командного боя нет.")
        return

    instance_id = call.data.split(":", 1)[1]
    finished, text = session.choose_actor(call.from_user.id, instance_id)
    if text is not None:
        update_battle_message(call.message.chat.id, call.message.message_id, session, text)
        return
    if finished:
        rpg_telegram_adapter.edit_message_text(session.get_state(), chat_id=call.message.chat.id, message_id=call.message.message_id)
        end_session(call.from_user.id)
        return
    update_battle_message(call.message.chat.id, call.message.message_id, session)


@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith("cg_team_action:"))
def choose_team_action(call):
    session = get_session(call.from_user.id)
    if not isinstance(session, TeamBattleSession):
        rpg_telegram_adapter.answer_callback_query(call.id, "Активного командного боя нет.")
        return

    action = call.data.split(":", 1)[1]
    if action == "back":
        if not session.go_back_to_actor_choice(call.from_user.id):
            rpg_telegram_adapter.answer_callback_query(call.id, "Сейчас нельзя вернуться назад.")
            return
        update_battle_message(call.message.chat.id, call.message.message_id, session)
        return

    if action not in session.get_available_actions(call.from_user.id):
        rpg_telegram_adapter.answer_callback_query(call.id, "Сейчас нельзя выбрать это действие.")
        return

    finished, text = session.choose_action(call.from_user.id, action)
    if text is not None:
        if finished:
            _log_battle_finished(session, chat_id=call.message.chat.id, trigger_user_id=call.from_user.id)
            rpg_telegram_adapter.edit_message_text(f"{text}\n\n{session.get_state()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
            end_session(call.from_user.id)
            return
        update_battle_message(call.message.chat.id, call.message.message_id, session, text)
        return

    update_battle_message(call.message.chat.id, call.message.message_id, session)


@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith("cg_team_target:"))
def choose_team_target(call):
    session = get_session(call.from_user.id)
    if not isinstance(session, TeamBattleSession):
        rpg_telegram_adapter.answer_callback_query(call.id, "Активного командного боя нет.")
        return

    target_id = call.data.split(":", 1)[1]
    finished, text = session.choose_target(call.from_user.id, target_id)
    if finished:
        _log_battle_finished(session, chat_id=call.message.chat.id, trigger_user_id=call.from_user.id)
        rpg_telegram_adapter.edit_message_text(f"{text}\n\n{session.get_state()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
        end_session(call.from_user.id)
        return

    update_battle_message(call.message.chat.id, call.message.message_id, session, text)
