"""Временное состояние карточных сценариев."""

from __future__ import annotations

from dataclasses import dataclass, field

MessageKey = tuple[int, int]


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


_pack_flows: dict[MessageKey, PackFlow] = {}
_lobbies: dict[MessageKey, ChallengeLobby] = {}
_user_lobbies: dict[int, MessageKey] = {}


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
