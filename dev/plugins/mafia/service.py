from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Role(str, Enum):
    CIVILIAN = "civilian"
    MAFIA = "mafia"
    DON = "don"
    SHERIFF = "sheriff"
    DOCTOR = "doctor"
    MANIAC = "maniac"

MAFIA_ALIGNED = {Role.MAFIA, Role.DON}


class Phase(str, Enum):
    LOBBY = "lobby"
    NIGHT = "night"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    FINISHED = "finished"


# --- Настройки партии. ---
MIN_PLAYERS = 4
MAX_PLAYERS = 14
LOBBY_SECONDS = 90
NIGHT_SECONDS = 45
DAY_DISCUSSION_SECONDS = 90
DAY_VOTE_SECONDS = 45


def build_role_set(player_count: int) -> list[Role]:
    """Формирует список ролей под конкретное число игроков.

    Соотношения — как в популярных мафия-ботах: примерно треть стола на
    мафию, отдельные роли открываются с ростом числа игроков.
    """
    if player_count < MIN_PLAYERS:
        raise ValueError("недостаточно игроков для партии")

    mafia_count = max(1, player_count // 3)
    roles: list[Role] = [Role.MAFIA] * mafia_count

    # На больших партиях один из мафии становится Доном (проверяет Комиссара)
    if player_count >= 8:
        roles[0] = Role.DON

    roles.append(Role.SHERIFF)
    if player_count >= 5:
        roles.append(Role.DOCTOR)
    if player_count >= 9:
        roles.append(Role.MANIAC)

    civilians_count = player_count - len(roles)
    roles.extend([Role.CIVILIAN] * civilians_count)

    random.shuffle(roles)
    return roles


@dataclass
class Player:
    user_id: int
    name: str
    role: Role = Role.CIVILIAN
    alive: bool = True


@dataclass
class MafiaGame:
    chat_id: int
    started_by: int
    phase: Phase = Phase.LOBBY
    day_number: int = 0
    players: dict[int, Player] = field(default_factory=dict)
    lobby_order: list[int] = field(default_factory=list)
    status_message_id: Optional[int] = None

    # Выбор за текущую ночь
    night_mafia_target: Optional[int] = None
    night_don_target: Optional[int] = None
    night_sheriff_target: Optional[int] = None
    night_doctor_target: Optional[int] = None
    night_maniac_target: Optional[int] = None

    # voter_id -> target_id за текущий день
    day_votes: dict[int, int] = field(default_factory=dict)

    timer_task: Optional[asyncio.Task] = None

    def alive_players(self) -> list[Player]:
        return [p for p in self.players.values() if p.alive]

    def alive_mafia(self) -> list[Player]:
        return [p for p in self.alive_players() if p.role in MAFIA_ALIGNED]

    def alive_maniac(self) -> list[Player]:
        return [p for p in self.alive_players() if p.role == Role.MANIAC]

    def alive_town(self) -> list[Player]:
        return [
            p for p in self.alive_players()
            if p.role not in MAFIA_ALIGNED and p.role != Role.MANIAC
        ]

    def check_winner(self) -> Optional[str]:
        """Возвращает 'mafia' / 'town' / 'maniac', либо None, если игра продолжается."""
        mafia = len(self.alive_mafia())
        maniac = len(self.alive_maniac())
        town = len(self.alive_town())

        if maniac and mafia == 0 and town == 0:
            return "maniac"
        if mafia == 0 and maniac == 0:
            return "town"
        if mafia > 0 and mafia >= town + maniac:
            return "mafia"
        return None


GAMES: dict[int, MafiaGame] = {}


def get_game(chat_id: int) -> Optional[MafiaGame]:
    return GAMES.get(chat_id)


def create_game(chat_id: int, started_by: int) -> MafiaGame:
    game = MafiaGame(chat_id=chat_id, started_by=started_by)
    GAMES[chat_id] = game
    return game


def remove_game(chat_id: int) -> None:
    GAMES.pop(chat_id, None)


def resolve_night(game: MafiaGame) -> list[Player]:
    """Считает жертв ночи, мутирует game.players, возвращает список погибших."""
    victims: set[int] = set()

    if game.night_mafia_target:
        victims.add(game.night_mafia_target)
    if game.night_maniac_target:
        victims.add(game.night_maniac_target)

    if game.night_doctor_target in victims:
        victims.discard(game.night_doctor_target)

    dead: list[Player] = []
    for user_id in victims:
        player = game.players.get(user_id)
        if player and player.alive:
            player.alive = False
            dead.append(player)

    game.night_mafia_target = None
    game.night_don_target = None
    game.night_sheriff_target = None
    game.night_doctor_target = None
    game.night_maniac_target = None
    return dead


def sheriff_check_result(game: MafiaGame, target_id: int) -> bool:
    """True, если проверяемый — из мафии (включая Дона)."""
    target = game.players.get(target_id)
    return bool(target and target.role in MAFIA_ALIGNED)


def don_check_result(game: MafiaGame, target_id: int) -> bool:
    """True, если проверяемый — Комиссар."""
    target = game.players.get(target_id)
    return bool(target and target.role == Role.SHERIFF)


def resolve_vote(game: MafiaGame) -> Optional[Player]:
    """Считает голоса дня и казнит лидера. При равенстве голосов — никто не умирает."""
    if not game.day_votes:
        return None

    tally: dict[int, int] = {}
    for target_id in game.day_votes.values():
        tally[target_id] = tally.get(target_id, 0) + 1

    top = max(tally.values())
    leaders = [user_id for user_id, count in tally.items() if count == top]
    game.day_votes.clear()

    if len(leaders) != 1:
        return None

    victim = game.players.get(leaders[0])
    if victim and victim.alive:
        victim.alive = False
        return victim
    return None