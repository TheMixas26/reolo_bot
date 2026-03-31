"""Inline-клавиатуры карточного режима."""

from __future__ import annotations

from telebot import types

from card_game.catalog import get_rarity_label


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
