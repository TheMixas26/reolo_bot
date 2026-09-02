from __future__ import annotations

ACTIVE_GAMES: dict[int, str] = {}

class ChatBusyError(Exception):
    """Класс ошибки, который говорит, что прямо сейчас что-то в чате уже проходит."""
    def __init__(self, chat_id: int, owner: str):
        self.chat_id = chat_id
        self.owner = owner
        super().__init__(f"Чат {chat_id} занят игрой '{owner}'")


def claim(chat_id: int, plugin_name: str) -> None:
    """
    Застолбить чат за конкретной игрой. Вызывает ChatBusyError,
    если чат уже занят другим плагином.
    """

    current = ACTIVE_GAMES.get(chat_id)

    if current and current != plugin_name:
        raise ChatBusyError(chat_id, current)
    
    ACTIVE_GAMES[chat_id] = plugin_name


def release(chat_id: int, plugin_name: str) -> None:
    """Освободить чат, ЕСЛИ ИМЕННО ТЫ его занял.
    Если кто-то другой - ничего не проихойдёт."""

    if ACTIVE_GAMES.get(chat_id) == plugin_name:
        ACTIVE_GAMES.pop(chat_id, None)


def current_game(chat_id: int) -> str | None:
    return ACTIVE_GAMES.get(chat_id)