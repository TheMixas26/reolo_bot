"""Совместимость со старым путём импорта."""

from card_game.services import list_packs, open_pack


def roll_card(user_id: int, pack_name: str | None = None):
    selected_pack = pack_name or next(iter(list_packs()), None)
    if selected_pack is None:
        raise ValueError("Нет доступных паков для открытия.")
    return open_pack(user_id, selected_pack)
