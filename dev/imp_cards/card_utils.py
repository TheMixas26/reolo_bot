"""Устаревшие консольные хелперы для ручной отладки карточной игры."""

from card_game.formatters import format_card_line


def display_cards(cards, title="Доступные карты"):
    """Печатает карты в консоль для ручной отладки."""
    print(f"\n{title}:")
    print("-" * 60)
    for index, card in enumerate(cards, start=1):
        print(f"{index:2}. {format_card_line(card)}")
    print("-" * 60)
