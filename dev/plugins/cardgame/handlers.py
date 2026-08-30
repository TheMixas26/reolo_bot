from __future__ import annotations
from varibles.dialogue_loader import TEXT
import asyncio
from core.core_plugin.stats import log_event, log_command_usage
from database.sqlite_db import create_user_if_missing
from plugins.bank.db import get_balance
from settings import RPG_BOT_NAME, RPG_BOT_USERNAME

from aiogram import Router, types
from aiogram.filters import Command
from aiogram import F

from .db import (
    get_inventory, add_card, get_all_cards,
    get_all_packs, close_card_event, 
    create_card_event, get_card_events, get_pack_by_name,
    update_card, update_pack, upsert_pack,
    reward_card_event_participant,
)

from .service import (
    get_lobby, get_pack_flow, clear_pack_flow,
    clear_lobby, format_pack_animation_frame,
    format_invite, format_lobby_ready,
    format_pack_menu, format_selection_prompt,
    build_duel_action_keyboard, build_duel_selection_keyboard,
    build_invite_keyboard, build_pack_keyboard,
    build_team_action_keyboard, build_team_actor_keyboard,
    build_team_selection_keyboard, build_team_target_keyboard,
    get_inventory, get_lobby_by_user, format_wallet,
    register_lobby, _log_battle_finished, register_pack_flow,
    clear_lobby_by_user, format_pack_result, format_admin_event_list,
    format_card_catalog, format_inventory, format_event_list,
    format_admin_pack_list, _find_card_in_inventory,
    _log_battle_started, _display_name, _ensure_user,
    _parse_card_fields, _reply_target, 
    _user_busy, _parse_update_fields, _selection_limit,
    
    
    TEAM_SIZE, purchase_and_open_pack, count_total_inventory_cards,
    get_session, DuelSession, end_session, TeamBattleSession,
    PackFlow, start_duel, start_team_battle, ChallengeLobby,
)



def register_handlers(context):
    admin = context.admin_id
    rpg_bot = context.rpg_bot

    rpg_router = Router(name="rpg-plugin")
    predlojka_router = Router(name="rpg-predlojka")

    async def _is_admin(message) -> bool:
        """
        Никогда. Вы слышите? НИКОГДА НЕ простите нейронки писать вам код.
        Вам же не нужны функции на одну строку, не имеющие смысла?
        """
        return message.from_user.id == admin

    async def send_pack_menu(chat_id: int, user_id: int, packs: list[dict]):
        balance = int(get_balance(user_id))
        return await rpg_bot.send_message(chat_id, format_pack_menu(packs, balance), parse_mode="HTML", reply_markup=build_pack_keyboard(packs))

    async def show_lobby_invite(lobby) -> None:
        await rpg_bot.edit_message_text(
            format_invite(lobby),
            chat_id=lobby.chat_id,
            message_id=lobby.message_id,
            parse_mode="HTML",
            reply_markup=build_invite_keyboard(),
        )

    async def show_lobby_selection(lobby) -> None:
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

        await rpg_bot.edit_message_text(
            format_selection_prompt(lobby, TEAM_SIZE),
            chat_id=lobby.chat_id,
            message_id=lobby.message_id,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    async def show_lobby_started(lobby, session) -> None:
        await rpg_bot.edit_message_text(
            f"{format_lobby_ready(lobby)}\n\n{session.get_state()}",
            chat_id=lobby.chat_id,
            message_id=lobby.message_id,
            reply_markup=get_battle_keyboard(session),
        )

    async def update_battle_message(chat_id: int, message_id: int, session, extra_text: str | None = None) -> None:
        text = session.get_state()
        if extra_text:
            text = f"{extra_text}\n\n{text}"
        reply_markup = None if session.finished else get_battle_keyboard(session)
        await rpg_bot.edit_message_text(
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

    @rpg_router.message(Command("cg_pack_cancel"))
    async def cancel_pack_selection(call):
        flow = get_pack_flow(call.message.chat.id, call.message.message_id)
        if flow is None:
            await rpg_bot.answer_callback_query(call.id, "Это окно паков уже неактивно.")
            return
        if call.from_user.id != flow.owner_id:
            await rpg_bot.answer_callback_query(call.id, "Этот пак выбирает другой игрок.")
            return

        clear_pack_flow(call.message.chat.id, call.message.message_id)
        log_event("pack_selection_cancelled", bot="rpg", user_id=call.from_user.id, chat_id=call.message.chat.id)
        await rpg_bot.edit_message_text("Открытие пака отменено.", chat_id=call.message.chat.id, message_id=call.message.message_id)


    @rpg_router.callback_query(F.data.startswith("cg_pack:"))
    async def open_selected_pack(call: types.CallbackQuery):
        # ! СИНХРОННАЯ ФУНКЦИЯ!!!!
        flow = get_pack_flow(call.message.chat.id, call.message.message_id)
        if flow is None:
            await call.answer("Это окно паков уже неактивно.", show_alert=False)
            return
        if call.from_user.id != flow.owner_id:
            await call.answer("Этот пак выбирает другой игрок.", show_alert=False)
            return

        try:
            pack_id = int(call.data.split(":", 1)[1])
        except (IndexError, ValueError):
            await call.answer("Ошибка: неверный формат пака.", show_alert=True)
            return

        pack = next((item for item in flow.packs if int(item["id"]) == pack_id), None)
        if pack is None:
            await call.answer("Такого пака здесь нет.", show_alert=False)
            return

        create_user_if_missing(
            call.from_user.id,
            call.from_user.first_name,
            call.from_user.last_name
        )

        pack_name = pack["name"]

        for step in range(1, 5):
            frame_text = format_pack_animation_frame(pack_name, step, 4)
            await call.message.edit_text(
                frame_text,
                parse_mode="HTML"
            )
            await asyncio.sleep(0.45)

        try:
            _, cards, balance_after = purchase_and_open_pack(call.from_user.id, pack_id)
        except ValueError as error:
            clear_pack_flow(call.message.chat.id, call.message.message_id)
            await rpg_bot.edit_message_text(str(error), chat_id=call.message.chat.id, message_id=call.message.message_id)
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
            await rpg_bot.edit_message_text(
                format_pack_result(pack_name, cards[:reveal_count], balance_after),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
            )
            await asyncio.sleep(0.35)

        clear_pack_flow(call.message.chat.id, call.message.message_id)

    @rpg_router.callback_query(F.text == "cg_invite_accept")
    async def accept_invite(call):
        lobby = get_lobby(call.message.chat.id, call.message.message_id)
        if lobby is None:
            await rpg_bot.answer_callback_query(call.id, "Этот вызов уже неактивен.")
            return
        if call.from_user.id != lobby.opponent_id:
            await rpg_bot.answer_callback_query(call.id, "Принять вызов может только приглашённый игрок.")
            return

        lobby.stage = "initiator_pick"
        log_event(
            "battle_challenge_accepted",
            bot="rpg",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={"mode": lobby.mode, "initiator_id": lobby.initiator_id, "opponent_id": lobby.opponent_id},
        )
        await show_lobby_selection(lobby)

    @rpg_router.callback_query(F.text == "cg_invite_decline")
    async def decline_invite(call):
        lobby = get_lobby(call.message.chat.id, call.message.message_id)
        if lobby is None:
            await rpg_bot.answer_callback_query(call.id, "Этот вызов уже неактивен.")
            return
        if call.from_user.id != lobby.opponent_id:
            await rpg_bot.answer_callback_query(call.id, "Отклонить вызов может только приглашённый игрок.")
            return

        clear_lobby(call.message.chat.id, call.message.message_id)
        log_event(
            "battle_challenge_declined",
            bot="rpg",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={"mode": lobby.mode, "initiator_id": lobby.initiator_id, "opponent_id": lobby.opponent_id},
        )
        await rpg_bot.edit_message_text(
            "Вызов отклонён.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    @rpg_router.callback_query(F.text == "cg_invite_cancel")
    async def cancel_invite(call):
        lobby = get_lobby(call.message.chat.id, call.message.message_id)
        if lobby is None:
            await rpg_bot.answer_callback_query(call.id, "Этот вызов уже неактивен.")
            return
        if call.from_user.id not in lobby.participant_ids():
            await rpg_bot.answer_callback_query(call.id, "Вы не участник этого вызова.")
            return

        clear_lobby(call.message.chat.id, call.message.message_id)
        log_event(
            "battle_challenge_cancelled",
            bot="rpg",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={"mode": lobby.mode, "initiator_id": lobby.initiator_id, "opponent_id": lobby.opponent_id},
        )
        await rpg_bot.edit_message_text(
            "Вызов отменён.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

    @rpg_router.callback_query(F.text == "cg_pick_wait")
    async def wait_for_full_team(call):
        await rpg_bot.answer_callback_query(call.id, f"Сначала нужно выбрать ровно {TEAM_SIZE} карт.")

    @rpg_router.callback_query(F.text == "cg_pick_reset")
    async def reset_selection(call):
        lobby = get_lobby(call.message.chat.id, call.message.message_id)
        if lobby is None:
            await rpg_bot.answer_callback_query(call.id, "Этот вызов уже неактивен.")
            return

        selector_id = lobby.current_selector_id()
        if selector_id != call.from_user.id:
            await rpg_bot.answer_callback_query(call.id, "Сейчас выбор делает другой игрок.")
            return

        lobby.reset_selection(call.from_user.id)
        await show_lobby_selection(lobby)


    @rpg_router.callback_query(F.data.startswith("cg_pick:"))
    async def pick_card(call):
        lobby = get_lobby(call.message.chat.id, call.message.message_id)
        if lobby is None:
            await rpg_bot.answer_callback_query(call.id, "Этот вызов уже неактивен.")
            return

        selector_id = lobby.current_selector_id()
        if selector_id != call.from_user.id:
            await rpg_bot.answer_callback_query(call.id, "Сейчас выбор делает другой игрок.")
            return

        card_id = int(call.data.split(":", 1)[1])
        card = _find_card_in_inventory(call.from_user.id, card_id)
        if card is None:
            await rpg_bot.answer_callback_query(call.id, "Этой карты нет в вашем инвентаре.")
            return

        selected_cards = lobby.get_selection(call.from_user.id)
        if lobby.mode == "team":
            selected_count = sum(1 for item in selected_cards if int(item["id"]) == card_id)
            if selected_count >= int(card.get("amount", 1)):
                await rpg_bot.answer_callback_query(call.id, "У вас больше нет свободных копий этой карты.")
                return

        if len(selected_cards) >= _selection_limit(lobby):
            await rpg_bot.answer_callback_query(call.id, "Лимит выбора уже достигнут.")
            return

        selected_cards.append(dict(card))
        if lobby.mode == "duel":
            if call.from_user.id == lobby.initiator_id:
                lobby.stage = "opponent_pick"
                await show_lobby_selection(lobby)
                return

            session = start_duel(
                lobby.initiator_id,
                lobby.initiator_name,
                lobby.initiator_selection[0],
                lobby.opponent_id,
                lobby.opponent_name,
                lobby.opponent_selection[0],
            )
            await show_lobby_started(lobby, session)
            _log_battle_started(session, call.message.chat.id)
            clear_lobby(call.message.chat.id, call.message.message_id)
            return

        await show_lobby_selection(lobby)

    @rpg_router.callback_query(F.text == "cg_pick_ready")
    async def confirm_pick(call):
        lobby = get_lobby(call.message.chat.id, call.message.message_id)
        if lobby is None:
            await rpg_bot.answer_callback_query(call.id, "Этот вызов уже неактивен.")
            return

        selector_id = lobby.current_selector_id()
        if selector_id != call.from_user.id:
            await rpg_bot.answer_callback_query(call.id, "Сейчас выбор делает другой игрок.")
            return
        if lobby.mode != "team":
            await rpg_bot.answer_callback_query(call.id, "Для дуэли достаточно выбрать одну карту.")
            return

        selected_cards = lobby.get_selection(call.from_user.id)
        if len(selected_cards) != TEAM_SIZE:
            await rpg_bot.answer_callback_query(call.id, f"Нужно выбрать ровно {TEAM_SIZE} карт.")
            return

        if call.from_user.id == lobby.initiator_id:
            lobby.stage = "opponent_pick"
            await show_lobby_selection(lobby)
            return

        session = start_team_battle(
            lobby.initiator_id,
            lobby.initiator_name,
            lobby.initiator_selection,
            lobby.opponent_id,
            lobby.opponent_name,
            lobby.opponent_selection,
        )
        await show_lobby_started(lobby, session)
        _log_battle_started(session, call.message.chat.id)
        clear_lobby(call.message.chat.id, call.message.message_id)

    @rpg_router.callback_query(F.text == "cg_battle_cancel")
    async def cancel_battle(call):
        session = get_session(call.from_user.id)
        if session is None:
            await rpg_bot.answer_callback_query(call.id, "Активного боя уже нет.")
            return

        log_event(
            "battle_cancelled",
            bot="rpg",
            user_id=call.from_user.id,
            chat_id=call.message.chat.id,
            metadata={"mode": session.mode, "source": "callback"},
        )
        end_session(call.from_user.id)
        await rpg_bot.edit_message_text("Бой отменён.", chat_id=call.message.chat.id, message_id=call.message.message_id)

    @rpg_router.callback_query(F.data.startswith("cg_duel_action:"))
    async def duel_action(call):
        session = get_session(call.from_user.id)
        if not isinstance(session, DuelSession):
            await rpg_bot.answer_callback_query(call.id, "Активной дуэли нет.")
            return

        action = call.data.split(":", 1)[1]
        if action not in session.get_available_actions(call.from_user.id):
            await rpg_bot.answer_callback_query(call.id, "Сейчас не ваш ход.")
            return

        finished, text = session.perform_action(call.from_user.id, action)
        if finished:
            _log_battle_finished(session, chat_id=call.message.chat.id, trigger_user_id=call.from_user.id)
            await rpg_bot.edit_message_text(f"{text}\n\n{session.get_state()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
            end_session(call.from_user.id)
            return

        await update_battle_message(call.message.chat.id, call.message.message_id, session, text)

    @rpg_router.callback_query(F.data.startswith("cg_team_actor:"))
    async def choose_team_actor(call):
        session = get_session(call.from_user.id)
        if not isinstance(session, TeamBattleSession):
            await rpg_bot.answer_callback_query(call.id, "Активного командного боя нет.")
            return

        instance_id = call.data.split(":", 1)[1]
        finished, text = session.choose_actor(call.from_user.id, instance_id)
        if text is not None:
            await update_battle_message(call.message.chat.id, call.message.message_id, session, text)
            return
        if finished:
            await rpg_bot.edit_message_text(session.get_state(), chat_id=call.message.chat.id, message_id=call.message.message_id)
            end_session(call.from_user.id)
            return
        await update_battle_message(call.message.chat.id, call.message.message_id, session)

    @rpg_router.callback_query(F.data.startswith("cg_team_action:"))
    async def choose_team_action(call):
        session = get_session(call.from_user.id)
        if not isinstance(session, TeamBattleSession):
            await rpg_bot.answer_callback_query(call.id, "Активного командного боя нет.")
            return

        action = call.data.split(":", 1)[1]
        if action == "back":
            if not session.go_back_to_actor_choice(call.from_user.id):
                await rpg_bot.answer_callback_query(call.id, "Сейчас нельзя вернуться назад.")
                return
            await update_battle_message(call.message.chat.id, call.message.message_id, session)
            return

        if action not in session.get_available_actions(call.from_user.id):
            await rpg_bot.answer_callback_query(call.id, "Сейчас нельзя выбрать это действие.")
            return

        finished, text = session.choose_action(call.from_user.id, action)
        if text is not None:
            if finished:
                _log_battle_finished(session, chat_id=call.message.chat.id, trigger_user_id=call.from_user.id)
                await rpg_bot.edit_message_text(f"{text}\n\n{session.get_state()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
                end_session(call.from_user.id)
                return
            await update_battle_message(call.message.chat.id, call.message.message_id, session, text)
            return

        await update_battle_message(call.message.chat.id, call.message.message_id, session)

    @rpg_router.message(Command("start"))
    async def start_command(message):
        log_command_usage("rpg", "start", message)
        _ensure_user(message)
        await rpg_bot.reply_to(message, "Добро пожаловать в карточную игру! Используйте /help, чтобы посмотреть команды.")

    @rpg_router.message(Command("help"))
    async def help_command(message):
        log_command_usage("rpg", "help", message)
        text = (
            "🎮 <b>Доступные команды:</b>\n"
            "/roll — выбрать и купить пак\n"
            "/packs — показать список паков\n"
            "/wallet — показать карточный бюджет\n"
            "/events — показать активные ивенты\n"
            "/inventory — показать ваши карты\n"
            "/cards — посмотреть каталог карт\n"
            "/duel — ответьте этой командой на сообщение другого игрока, чтобы вызвать его на дуэль\n"
            "/team_battle — ответьте этой командой на сообщение другого игрока, чтобы начать командный бой 5 на 5\n"
            "/cancel — отменить ваш текущий вызов или бой"
        )
        await rpg_bot.send_message(message.chat.id, text, parse_mode="HTML")

    @rpg_router.message(Command("cancel"))
    async def cancel_command(message):
        log_command_usage("rpg", "cancel", message)
        user_id = message.from_user.id
        had_active_flow = get_session(user_id) is not None or get_lobby_by_user(user_id) is not None
        clear_lobby_by_user(user_id)
        end_session(user_id)
        if had_active_flow:
            log_event("battle_cancelled", bot="rpg", user_id=user_id, chat_id=message.chat.id, metadata={"source": "command"})
        await rpg_bot.reply_to(message, "Ваше текущее карточное действие отменено.")

    @rpg_router.message(Command("roll", "packs"))
    async def roll_command(message):
        log_command_usage("rpg", "roll" if message.text.startswith("/roll") else "packs", message)
        _ensure_user(message)
        packs = get_all_packs(active_only=True)
        if not packs:
            await rpg_bot.reply_to(message, "Паки пока не настроены.")
            return

        sent_message = await send_pack_menu(message.chat.id, message.from_user.id, packs)
        register_pack_flow(PackFlow(message.from_user.id, sent_message.chat.id, sent_message.message_id, packs))

    @rpg_router.message(Command("wallet"))
    async def wallet_command(message):
        log_command_usage("rpg", "wallet", message)
        _ensure_user(message)
        balance = int(get_balance(message.from_user.id))
        await rpg_bot.send_message(message.chat.id, format_wallet(balance), parse_mode="HTML")

    @rpg_router.message(Command("events"))
    async def events_command(message):
        log_command_usage("rpg", "events", message)
        events = get_card_events(status="active")
        await rpg_bot.send_message(message.chat.id, format_event_list(events), parse_mode="HTML")

    @rpg_router.message(Command("inv", "inventory"))
    async def inventory_command(message):
        log_command_usage("rpg", "inventory", message)
        _ensure_user(message)
        inventory = get_inventory(message.from_user.id)
        if not inventory:
            await rpg_bot.reply_to(message, "Ваш инвентарь пуст. Откройте первый пак через /roll.")
            return
        await rpg_bot.send_message(message.chat.id, format_inventory(inventory), parse_mode="HTML")

    @rpg_router.message(Command("cards"))
    async def cards_command(message):
        log_command_usage("rpg", "cards", message)
        cards = get_all_cards()
        await rpg_bot.send_message(message.chat.id, format_card_catalog(cards), parse_mode="HTML")

    @rpg_router.message(Command("duel"))
    async def duel_command(message):
        log_command_usage("rpg", "duel", message)
        _ensure_user(message)
        opponent = _reply_target(message)
        if opponent is None:
            await rpg_bot.reply_to(message, "Для дуэли ответьте командой /duel на сообщение другого игрока.")
            return

        create_user_if_missing(opponent.id, opponent.first_name, opponent.last_name)
        challenger_inventory = get_inventory(message.from_user.id)
        opponent_inventory = get_inventory(opponent.id)
        if not challenger_inventory:
            await rpg_bot.reply_to(message, "У вас нет карт для дуэли. Откройте пак через /roll.")
            return
        if not opponent_inventory:
            await rpg_bot.reply_to(message, "У второго игрока пока нет карт для дуэли.")
            return
        if _user_busy(message.from_user.id) or _user_busy(opponent.id):
            await rpg_bot.reply_to(message, "Один из игроков уже занят другим карточным действием.")
            return

        placeholder = await rpg_bot.send_message(message.chat.id, "Создаю дуэльный вызов...")
        lobby = ChallengeLobby(
            mode="duel",
            chat_id=placeholder.chat.id,
            message_id=placeholder.message_id,
            initiator_id=message.from_user.id,
            initiator_name=_display_name(message.from_user),
            opponent_id=opponent.id,
            opponent_name=_display_name(opponent),
        )
        register_lobby(lobby)
        await show_lobby_invite(lobby)
        log_event(
            "battle_challenge_created",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"mode": "duel", "opponent_id": opponent.id},
        )

    @rpg_router.message(Command("team_battle"))
    async def team_battle_command(message):
        log_command_usage("rpg", "team_battle", message)
        _ensure_user(message)
        opponent = _reply_target(message)
        if opponent is None:
            await rpg_bot.reply_to(message, "Для командного боя ответьте командой /team_battle на сообщение другого игрока.")
            return

        create_user_if_missing(opponent.id, opponent.first_name, opponent.last_name)
        challenger_inventory = get_inventory(message.from_user.id)
        opponent_inventory = get_inventory(opponent.id)
        if count_total_inventory_cards(challenger_inventory) < TEAM_SIZE:
            await rpg_bot.reply_to(message, f"Для командного боя нужно минимум {TEAM_SIZE} карт в инвентаре.")
            return
        if count_total_inventory_cards(opponent_inventory) < TEAM_SIZE:
            await rpg_bot.reply_to(message, "У второго игрока пока недостаточно карт для командного боя.")
            return
        if _user_busy(message.from_user.id) or _user_busy(opponent.id):
            await rpg_bot.reply_to(message, "Один из игроков уже занят другим карточным действием.")
            return

        placeholder = await rpg_bot.send_message(message.chat.id, "Создаю командный вызов...")
        lobby = ChallengeLobby(
            mode="team",
            chat_id=placeholder.chat.id,
            message_id=placeholder.message_id,
            initiator_id=message.from_user.id,
            initiator_name=_display_name(message.from_user),
            opponent_id=opponent.id,
            opponent_name=_display_name(opponent),
        )
        register_lobby(lobby)
        await show_lobby_invite(lobby)
        log_event(
            "battle_challenge_created",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"mode": "team", "opponent_id": opponent.id},
        )

    @rpg_router.message(Command("cg_events_admin"))
    async def events_admin_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_events_admin", message)
        await rpg_bot.reply_to(message, format_admin_event_list(get_card_events()), parse_mode="HTML")

    @rpg_router.message(Command("cg_create_event"))
    async def create_event_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_create_event", message)

        if " " not in message.text:
            await rpg_bot.reply_to(message, "Введите данные ивента в формате:\nНазвание | Награда | Описание")
            rpg_bot.register_next_step_handler(message, create_event_from_step)
            return

        await _create_event_from_payload(message, message.text.split(" ", 1)[1])



    @rpg_router.callback_query(lambda c: c.data.startswith("cg_team_target:"))
    async def choose_team_target(call):
        session = get_session(call.from_user.id)
        if not isinstance(session, TeamBattleSession):
            await rpg_bot.answer_callback_query(call.id, "Активного командного боя нет.")
            return

        target_id = call.data.split(":", 1)[1]
        finished, text = session.choose_target(call.from_user.id, target_id)
        if finished:
            _log_battle_finished(session, chat_id=call.message.chat.id, trigger_user_id=call.from_user.id)
            await rpg_bot.edit_message_text(f"{text}\n\n{session.get_state()}", chat_id=call.message.chat.id, message_id=call.message.message_id)
            end_session(call.from_user.id)
            return

        await update_battle_message(call.message.chat.id, call.message.message_id, session, text)

    async def create_event_from_step(message):
        if not await _is_admin(message):
            return
        await _create_event_from_payload(message, message.text)

    async def _create_event_from_payload(message, payload: str):
        try:
            title, reward, description = [part.strip() for part in payload.split("|", 2)]
            event_id = create_card_event(title, int(reward), description)
            await rpg_bot.reply_to(message, f"Карточный ивент создан: #{event_id} {title}")
            log_event(
                "card_event_created",
                bot="rpg",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"event_id": event_id, "title": title, "reward": int(reward)},
            )
        except ValueError:
            await rpg_bot.reply_to(message, "Формат: /cg_create_event Название | Награда | Описание")

    @rpg_router.message(Command("cg_close_event"))
    async def close_event_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_close_event", message)

        try:
            _, raw_event_id = message.text.split(" ", 1)
            event_id = int(raw_event_id.strip())
            close_card_event(event_id)
            await rpg_bot.reply_to(message, "Ивент закрыт.")
            log_event("card_event_closed", bot="rpg", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"event_id": event_id})
        except ValueError:
            await rpg_bot.reply_to(message, "Формат: /cg_close_event ID_ивента")

    @rpg_router.message(Command("cg_reward_event"))
    async def reward_event_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_reward_event", message)

        target = _reply_target(message)
        if target is None:
            await rpg_bot.reply_to(message, "Ответьте этой командой на сообщение участника: /cg_reward_event ID_ивента")
            return

        try:
            _, raw_event_id = message.text.split(" ", 1)
            event_id = int(raw_event_id.strip())
            create_user_if_missing(target.id, target.first_name, target.last_name)
            granted, reward = reward_card_event_participant(event_id, target.id)
            if granted:
                await rpg_bot.reply_to(message, f"Игрок получил {reward} Имперских Батов за участие в ивенте #{event_id}.")
                log_event(
                    "event_reward_granted",
                    bot="rpg",
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    metadata={"event_id": event_id, "target_user_id": target.id, "reward": reward},
                )
            else:
                await rpg_bot.reply_to(message, "Этому игроку награда за данный ивент уже выдавалась.")
        except ValueError as error:
            await rpg_bot.reply_to(message, f"Ошибка: {error}")

    @rpg_router.message(Command("cg+packs_admin"))
    async def packs_admin_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_packs_admin", message)
        await rpg_bot.reply_to(message, format_admin_pack_list(get_all_packs()))

    @rpg_router.message(Command("cg_add_pack"))
    async def add_pack_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_add_pack", message)

        try:
            _, payload = message.text.split(" ", 1)
            name, price, description = [part.strip() for part in payload.split("|", 2)]
            upsert_pack(name, int(price), description, True)
            await rpg_bot.reply_to(message, f"Пак «{name}» создан или обновлён.")
            log_event(
                "pack_upserted",
                bot="rpg",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"name": name, "price": int(price)},
            )
        except ValueError:
            await rpg_bot.reply_to(message, "Формат: /cg_add_pack Название | Цена | Описание")

    @rpg_router.message(Command("cg_edit_pack"))
    async def edit_pack_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_edit_pack", message)

        try:
            _, payload = message.text.split(" ", 1)
            parts = [part.strip() for part in payload.split("|")]
            pack_id = int(parts[0])
            updates = _parse_update_fields(parts[1:])
            update_pack(pack_id, **updates)
            await rpg_bot.reply_to(message, f"Пак #{pack_id} обновлён.")
            log_event(
                "pack_updated",
                bot="rpg",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"pack_id": pack_id, "fields": sorted(updates.keys())},
            )
        except ValueError as error:
            await rpg_bot.reply_to(message, f"Формат: /cg_edit_pack ID | price=50 | description=... | is_active=1 | name=...\nОшибка: {error}")

    @rpg_router.message(Command("cg_add_card"))
    async def add_card_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_add_card", message)

        try:
            _, payload = message.text.split(" ", 1)
            parts = [part.strip() for part in payload.split("|", 9)]
            card_data = _parse_card_fields(parts)
            if get_pack_by_name(card_data["category"]) is None:
                await rpg_bot.reply_to(message, "Сначала создайте пак для этой категории через /cg_add_pack.")
                return
            card_id = add_card(card_data)
            await rpg_bot.reply_to(message, f"Карта добавлена с id #{card_id}.")
            log_event(
                "card_created",
                bot="rpg",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"card_id": card_id, "name": card_data["name"], "category": card_data["category"]},
            )
        except ValueError as error:
            await rpg_bot.reply_to(
                message,
                "Формат: /cg_add_card Имя | Редкость | HP | ATK | DEF | TYPE | Пак | ability | image | desc\n"
                f"Ошибка: {error}",
            )

    @rpg_router.message(Command("cg_edit_card"))
    async def edit_card_command(message):
        if not await _is_admin(message):
            return
        log_command_usage("rpg", "cg_edit_card", message)

        try:
            _, payload = message.text.split(" ", 1)
            parts = [part.strip() for part in payload.split("|")]
            card_id = int(parts[0])
            updates = _parse_update_fields(parts[1:])
            if "category" in updates and updates["category"] and get_pack_by_name(updates["category"]) is None:
                await rpg_bot.reply_to(message, "Указанный пак не существует. Сначала создайте его через /cg_add_pack.")
                return
            update_card(card_id, updates)
            await rpg_bot.reply_to(message, f"Карта #{card_id} обновлена.")
            log_event(
                "card_updated",
                bot="rpg",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"card_id": card_id, "fields": sorted(updates.keys())},
            )
        except ValueError as error:
            await rpg_bot.reply_to(
                message,
                "Формат: /cg_edit_card ID | hp=500 | atk=120 | rarity=4-SR | category=Новый пак\n"
                f"Ошибка: {error}",
            )

    @predlojka_router.message(Command("battle"))
    async def redirect_to_rpg_bot(message):
        log_command_usage("predlojka", "battle", message)
        context.predlojka_bot.reply_to(
            message,
            # TODO: перенести в texts.json
            f"Притормози, дружище! Вся RPG система переехала в {RPG_BOT_NAME}. "
            f"Не волнуйся, формально это всё ещё я, просто вынесенная часть проекта. "
            f"Бегом в него!\n\n{RPG_BOT_USERNAME}"
        )
