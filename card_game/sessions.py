"""Хранилище активных игровых сессий."""

from __future__ import annotations

from card_game.battle import DuelSession, TeamBattleSession

GameSession = DuelSession | TeamBattleSession

_active_sessions: dict[int, GameSession] = {}


def start_duel(
    player1_id: int,
    player1_name: str,
    player1_card: dict,
    player2_id: int,
    player2_name: str,
    player2_card: dict,
) -> DuelSession:
    session = DuelSession(player1_id, player1_name, player1_card, player2_id, player2_name, player2_card)
    for user_id in session.get_participant_ids():
        _active_sessions[user_id] = session
    return session


def start_team_battle(
    player1_id: int,
    player1_name: str,
    team1_cards: list[dict],
    player2_id: int,
    player2_name: str,
    team2_cards: list[dict],
) -> TeamBattleSession:
    session = TeamBattleSession(player1_id, player1_name, team1_cards, player2_id, player2_name, team2_cards)
    for user_id in session.get_participant_ids():
        _active_sessions[user_id] = session
    return session


def get_session(user_id: int) -> GameSession | None:
    return _active_sessions.get(user_id)


def end_session(user_id: int) -> None:
    session = _active_sessions.get(user_id)
    if session is None:
        return
    for participant_id in session.get_participant_ids():
        _active_sessions.pop(participant_id, None)
