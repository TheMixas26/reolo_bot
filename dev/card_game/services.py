"""Сервисные функции карточной игры."""

from __future__ import annotations

import random

from card_game.catalog import RARITY_WEIGHTS, get_rarity_label
from database.sqlite_db import add_to_inventory, get_balance, get_cards_by_category, get_pack_by_id, get_pack_names, set_balance

TEAM_SIZE = 5
PACK_SIZE = 3


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
