from typing import Dict, Optional
from imp_cards.battle import DuelSession, TeamBattleSession

# Хранилище активных сессий
active_sessions: Dict[int, object] = {}  # key = user_id

def start_duel(user_id: int, player_card: dict, enemy_card: dict) -> DuelSession:
    """Создаёт новую дуэльную сессию для пользователя."""
    session = DuelSession(player_card, enemy_card)
    active_sessions[user_id] = session
    return session

def start_team_battle(user_id: int, team1: list, team2: list) -> TeamBattleSession:
    """Создаёт новую сессию командного боя."""
    session = TeamBattleSession(team1, team2)
    active_sessions[user_id] = session
    return session

def get_session(user_id: int) -> Optional[object]:
    """Возвращает активную сессию пользователя."""
    return active_sessions.get(user_id)

def end_session(user_id: int):
    """Завершает сессию (удаляет из словаря)."""
    if user_id in active_sessions:
        del active_sessions[user_id]