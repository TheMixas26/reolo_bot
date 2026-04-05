"""Команды карточного бота."""

from __future__ import annotations

from analytics.stats import log_command_usage, log_event
from config import admin, rpg_bot
from database.sqlite_db import (
    add_card,
    create_card_event,
    create_user_if_missing,
    get_all_cards,
    get_all_packs,
    get_balance,
    get_card_events,
    get_inventory,
    get_pack_by_name,
    reward_card_event_participant,
    update_card,
    update_pack,
    upsert_pack,
    close_card_event,
)

from card_game.formatters import (
    format_admin_event_list,
    format_admin_pack_list,
    format_card_catalog,
    format_event_list,
    format_inventory,
    format_wallet,
)
from card_game.services import TEAM_SIZE, count_total_inventory_cards
from card_game.sessions import end_session, get_session
from handlers.card_handlers.state import (
    ChallengeLobby,
    PackFlow,
    clear_lobby_by_user,
    get_lobby_by_user,
    register_lobby,
    register_pack_flow,
)
from handlers.card_handlers.ui import send_pack_menu, show_lobby_invite
from posting.runtime import rpg_telegram_adapter


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


def _is_admin(message) -> bool:
    return message.from_user.id == admin


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


@rpg_bot.message_handler(commands=["start"])
def start_command(message):
    log_command_usage("rpg", "start", message)
    _ensure_user(message)
    rpg_telegram_adapter.reply_to(message, "Добро пожаловать в карточную игру! Используйте /help, чтобы посмотреть команды.")


@rpg_bot.message_handler(commands=["help"])
def help_command(message):
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
    rpg_telegram_adapter.send_message(message.chat.id, text, parse_mode="HTML")


@rpg_bot.message_handler(commands=["cancel"])
def cancel_command(message):
    log_command_usage("rpg", "cancel", message)
    user_id = message.from_user.id
    had_active_flow = get_session(user_id) is not None or get_lobby_by_user(user_id) is not None
    clear_lobby_by_user(user_id)
    end_session(user_id)
    if had_active_flow:
        log_event("battle_cancelled", bot="rpg", user_id=user_id, chat_id=message.chat.id, metadata={"source": "command"})
    rpg_telegram_adapter.reply_to(message, "Ваше текущее карточное действие отменено.")


@rpg_bot.message_handler(commands=["roll", "packs"])
def roll_command(message):
    log_command_usage("rpg", "roll" if message.text.startswith("/roll") else "packs", message)
    _ensure_user(message)
    packs = get_all_packs(active_only=True)
    if not packs:
        rpg_telegram_adapter.reply_to(message, "Паки пока не настроены.")
        return

    sent_message = send_pack_menu(message.chat.id, message.from_user.id, packs)
    register_pack_flow(PackFlow(message.from_user.id, sent_message.chat.id, sent_message.message_id, packs))


@rpg_bot.message_handler(commands=["wallet"])
def wallet_command(message):
    log_command_usage("rpg", "wallet", message)
    _ensure_user(message)
    balance = int(get_balance(message.from_user.id))
    rpg_telegram_adapter.send_message(message.chat.id, format_wallet(balance), parse_mode="HTML")


@rpg_bot.message_handler(commands=["events"])
def events_command(message):
    log_command_usage("rpg", "events", message)
    events = get_card_events(status="active")
    rpg_telegram_adapter.send_message(message.chat.id, format_event_list(events), parse_mode="HTML")


@rpg_bot.message_handler(commands=["inventory"])
def inventory_command(message):
    log_command_usage("rpg", "inventory", message)
    _ensure_user(message)
    inventory = get_inventory(message.from_user.id)
    if not inventory:
        rpg_telegram_adapter.reply_to(message, "Ваш инвентарь пуст. Откройте первый пак через /roll.")
        return
    rpg_telegram_adapter.send_message(message.chat.id, format_inventory(inventory), parse_mode="HTML")


@rpg_bot.message_handler(commands=["cards"])
def cards_command(message):
    log_command_usage("rpg", "cards", message)
    cards = get_all_cards()
    rpg_telegram_adapter.send_message(message.chat.id, format_card_catalog(cards), parse_mode="HTML")


@rpg_bot.message_handler(commands=["duel"])
def duel_command(message):
    log_command_usage("rpg", "duel", message)
    _ensure_user(message)
    opponent = _reply_target(message)
    if opponent is None:
        rpg_telegram_adapter.reply_to(message, "Для дуэли ответьте командой /duel на сообщение другого игрока.")
        return

    create_user_if_missing(opponent.id, opponent.first_name, opponent.last_name)
    challenger_inventory = get_inventory(message.from_user.id)
    opponent_inventory = get_inventory(opponent.id)
    if not challenger_inventory:
        rpg_telegram_adapter.reply_to(message, "У вас нет карт для дуэли. Откройте пак через /roll.")
        return
    if not opponent_inventory:
        rpg_telegram_adapter.reply_to(message, "У второго игрока пока нет карт для дуэли.")
        return
    if _user_busy(message.from_user.id) or _user_busy(opponent.id):
        rpg_telegram_adapter.reply_to(message, "Один из игроков уже занят другим карточным действием.")
        return

    placeholder = rpg_telegram_adapter.send_message(message.chat.id, "Создаю дуэльный вызов...")
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
    show_lobby_invite(lobby)
    log_event(
        "battle_challenge_created",
        bot="rpg",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"mode": "duel", "opponent_id": opponent.id},
    )


@rpg_bot.message_handler(commands=["team_battle"])
def team_battle_command(message):
    log_command_usage("rpg", "team_battle", message)
    _ensure_user(message)
    opponent = _reply_target(message)
    if opponent is None:
        rpg_telegram_adapter.reply_to(message, "Для командного боя ответьте командой /team_battle на сообщение другого игрока.")
        return

    create_user_if_missing(opponent.id, opponent.first_name, opponent.last_name)
    challenger_inventory = get_inventory(message.from_user.id)
    opponent_inventory = get_inventory(opponent.id)
    if count_total_inventory_cards(challenger_inventory) < TEAM_SIZE:
        rpg_telegram_adapter.reply_to(message, f"Для командного боя нужно минимум {TEAM_SIZE} карт в инвентаре.")
        return
    if count_total_inventory_cards(opponent_inventory) < TEAM_SIZE:
        rpg_telegram_adapter.reply_to(message, "У второго игрока пока недостаточно карт для командного боя.")
        return
    if _user_busy(message.from_user.id) or _user_busy(opponent.id):
        rpg_telegram_adapter.reply_to(message, "Один из игроков уже занят другим карточным действием.")
        return

    placeholder = rpg_telegram_adapter.send_message(message.chat.id, "Создаю командный вызов...")
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
    show_lobby_invite(lobby)
    log_event(
        "battle_challenge_created",
        bot="rpg",
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        metadata={"mode": "team", "opponent_id": opponent.id},
    )


@rpg_bot.message_handler(commands=["cg_events_admin"])
def events_admin_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_events_admin", message)
    rpg_telegram_adapter.reply_to(message, format_admin_event_list(get_card_events()), parse_mode="HTML")


@rpg_bot.message_handler(commands=["cg_create_event"])
def create_event_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_create_event", message)

    if " " not in message.text:
        rpg_telegram_adapter.reply_to(message, "Введите данные ивента в формате:\nНазвание | Награда | Описание")
        rpg_bot.register_next_step_handler(message, create_event_from_step)
        return

    _create_event_from_payload(message, message.text.split(" ", 1)[1])


def create_event_from_step(message):
    if not _is_admin(message):
        return
    _create_event_from_payload(message, message.text)


def _create_event_from_payload(message, payload: str):
    try:
        title, reward, description = [part.strip() for part in payload.split("|", 2)]
        event_id = create_card_event(title, int(reward), description)
        rpg_telegram_adapter.reply_to(message, f"Карточный ивент создан: #{event_id} {title}")
        log_event(
            "card_event_created",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"event_id": event_id, "title": title, "reward": int(reward)},
        )
    except ValueError:
        rpg_telegram_adapter.reply_to(message, "Формат: /cg_create_event Название | Награда | Описание")


@rpg_bot.message_handler(commands=["cg_close_event"])
def close_event_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_close_event", message)

    try:
        _, raw_event_id = message.text.split(" ", 1)
        event_id = int(raw_event_id.strip())
        close_card_event(event_id)
        rpg_telegram_adapter.reply_to(message, "Ивент закрыт.")
        log_event("card_event_closed", bot="rpg", user_id=message.from_user.id, chat_id=message.chat.id, metadata={"event_id": event_id})
    except ValueError:
        rpg_telegram_adapter.reply_to(message, "Формат: /cg_close_event ID_ивента")


@rpg_bot.message_handler(commands=["cg_reward_event"])
def reward_event_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_reward_event", message)

    target = _reply_target(message)
    if target is None:
        rpg_telegram_adapter.reply_to(message, "Ответьте этой командой на сообщение участника: /cg_reward_event ID_ивента")
        return

    try:
        _, raw_event_id = message.text.split(" ", 1)
        event_id = int(raw_event_id.strip())
        create_user_if_missing(target.id, target.first_name, target.last_name)
        granted, reward = reward_card_event_participant(event_id, target.id)
        if granted:
            rpg_telegram_adapter.reply_to(message, f"Игрок получил {reward} Имперских Батов за участие в ивенте #{event_id}.")
            log_event(
                "event_reward_granted",
                bot="rpg",
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                metadata={"event_id": event_id, "target_user_id": target.id, "reward": reward},
            )
        else:
            rpg_telegram_adapter.reply_to(message, "Этому игроку награда за данный ивент уже выдавалась.")
    except ValueError as error:
        rpg_telegram_adapter.reply_to(message, f"Ошибка: {error}")


@rpg_bot.message_handler(commands=["cg_packs_admin"])
def packs_admin_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_packs_admin", message)
    rpg_telegram_adapter.reply_to(message, format_admin_pack_list(get_all_packs()))


@rpg_bot.message_handler(commands=["cg_add_pack"])
def add_pack_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_add_pack", message)

    try:
        _, payload = message.text.split(" ", 1)
        name, price, description = [part.strip() for part in payload.split("|", 2)]
        upsert_pack(name, int(price), description, True)
        rpg_telegram_adapter.reply_to(message, f"Пак «{name}» создан или обновлён.")
        log_event(
            "pack_upserted",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"name": name, "price": int(price)},
        )
    except ValueError:
        rpg_telegram_adapter.reply_to(message, "Формат: /cg_add_pack Название | Цена | Описание")


@rpg_bot.message_handler(commands=["cg_edit_pack"])
def edit_pack_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_edit_pack", message)

    try:
        _, payload = message.text.split(" ", 1)
        parts = [part.strip() for part in payload.split("|")]
        pack_id = int(parts[0])
        updates = _parse_update_fields(parts[1:])
        update_pack(pack_id, **updates)
        rpg_telegram_adapter.reply_to(message, f"Пак #{pack_id} обновлён.")
        log_event(
            "pack_updated",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"pack_id": pack_id, "fields": sorted(updates.keys())},
        )
    except ValueError as error:
        rpg_telegram_adapter.reply_to(message, f"Формат: /cg_edit_pack ID | price=50 | description=... | is_active=1 | name=...\nОшибка: {error}")


@rpg_bot.message_handler(commands=["cg_add_card"])
def add_card_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_add_card", message)

    try:
        _, payload = message.text.split(" ", 1)
        parts = [part.strip() for part in payload.split("|", 9)]
        card_data = _parse_card_fields(parts)
        if get_pack_by_name(card_data["category"]) is None:
            rpg_telegram_adapter.reply_to(message, "Сначала создайте пак для этой категории через /cg_add_pack.")
            return
        card_id = add_card(card_data)
        rpg_telegram_adapter.reply_to(message, f"Карта добавлена с id #{card_id}.")
        log_event(
            "card_created",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"card_id": card_id, "name": card_data["name"], "category": card_data["category"]},
        )
    except ValueError as error:
        rpg_telegram_adapter.reply_to(
            message,
            "Формат: /cg_add_card Имя | Редкость | HP | ATK | DEF | TYPE | Пак | ability | image | desc\n"
            f"Ошибка: {error}",
        )


@rpg_bot.message_handler(commands=["cg_edit_card"])
def edit_card_command(message):
    if not _is_admin(message):
        return
    log_command_usage("rpg", "cg_edit_card", message)

    try:
        _, payload = message.text.split(" ", 1)
        parts = [part.strip() for part in payload.split("|")]
        card_id = int(parts[0])
        updates = _parse_update_fields(parts[1:])
        if "category" in updates and updates["category"] and get_pack_by_name(updates["category"]) is None:
            rpg_telegram_adapter.reply_to(message, "Указанный пак не существует. Сначала создайте его через /cg_add_pack.")
            return
        update_card(card_id, updates)
        rpg_telegram_adapter.reply_to(message, f"Карта #{card_id} обновлена.")
        log_event(
            "card_updated",
            bot="rpg",
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            metadata={"card_id": card_id, "fields": sorted(updates.keys())},
        )
    except ValueError as error:
        rpg_telegram_adapter.reply_to(
            message,
            "Формат: /cg_edit_card ID | hp=500 | atk=120 | rarity=4-SR | category=Новый пак\n"
            f"Ошибка: {error}",
        )
