import random
from typing import Optional, Tuple, List, Dict, Any
from imp_cards.models import BattleCard

class DuelSession:
    """Управляет одной дуэлью между игроком и врагом."""
    def __init__(self, player_card_data: dict, enemy_card_data: dict):
        self.player = BattleCard(player_card_data)
        self.enemy = BattleCard(enemy_card_data)
        self.first = random.choice(['player', 'enemy'])
        self.turn = 0
        self.finished = False
        self.winner = None
        self.last_action_message = ""

    def get_state(self) -> str:
        """Возвращает строку текущего состояния боя."""
        lines = []
        lines.append(f"ИГРОК: {self.player.get_stats_string()}")
        lines.append(f"ПРОТИВНИК: {self.enemy.get_stats_string()}")
        lines.append(f"Ход: {self.turn+1}")
        if self.last_action_message:
            lines.append(self.last_action_message)
        return "\n".join(lines)

    def get_available_actions(self) -> List[str]:
        """Возвращает список доступных действий для игрока."""
        if self.finished or self.player.stun:
            return []  # если бой закончен или игрок оглушён, действий нет
        return ['attack', 'defend']

    def player_action(self, action: str) -> Tuple[bool, str]:
        """
        Обрабатывает действие игрока.
        Возвращает (бой_завершён?, сообщение_для_пользователя)
        """
        if self.finished:
            return True, "Бой уже закончен."

        # Обработка хода игрока
        msg = self._process_turn('player', action)

        # Проверка победы
        if not self.enemy.is_alive():
            self.finished = True
            self.winner = 'player'
            return True, f"{msg}\n\n🎉 ПОБЕДА! {self.player.name} одержал победу!"

        # Ход врага (если игра не закончена)
        if not self.finished:
            enemy_action = self._enemy_ai()
            enemy_msg = self._process_turn('enemy', enemy_action)
            msg += "\n" + enemy_msg

            if not self.player.is_alive():
                self.finished = True
                self.winner = 'enemy'
                return True, f"{msg}\n\n💀 ПОРАЖЕНИЕ! {self.enemy.name} одержал победу!"

        self.turn += 1
        return False, msg

    def _process_turn(self, who: str, action: str) -> str:
        """Выполняет действие для указанного персонажа."""
        if who == 'player':
            actor = self.player
            target = self.enemy
        else:
            actor = self.enemy
            target = self.player

        # Оглушение
        if actor.stun:
            actor.clear_stun()
            return f"⏭️ {actor.name} ОГЛУШЕН и пропускает ход!"

        if action == 'attack':
            base_damage = actor.atk
            damage, crit = self._calc_critical(base_damage)
            stun_chance = 0.1
            stun_occurred = random.random() < stun_chance
            if stun_occurred:
                target.apply_stun()
            final_damage = target.take_damage(damage)
            crit_msg = " 💥КРИТИЧЕСКИЙ!💥" if crit else ""
            stun_msg = " и ОГЛУШЕН!" if stun_occurred else ""
            return f"⚔️ {actor.name} наносит {final_damage} урона{crit_msg} {target.name}{stun_msg}"

        elif action == 'defend':
            actor.set_def_bonus()
            return f"🛡️ {actor.name} использует защиту (+{actor.def_bonus} к защите)"

        return "Неизвестное действие"

    def _enemy_ai(self) -> str:
        """Простейший AI врага."""
        if self.enemy.hp < self.enemy.max_hp * 0.5 and self.player.atk > self.enemy.atk:
            return 'defend'
        else:
            return 'attack'

    @staticmethod
    def _calc_critical(damage):
        if random.random() < 0.1:
            return damage * 2, True
        return damage, False


class TeamBattleSession:
    """Управляет командным боем 5 на 5."""
    def __init__(self, team1_data: List[dict], team2_data: List[dict]):
        self.team1 = [BattleCard(card) for card in team1_data]
        self.team2 = [BattleCard(card) for card in team2_data]
        self.first_team = random.choice([1, 2])
        self.turn = 0
        self.finished = False
        self.winner = None
        self.last_action_message = ""

        self.active1 = self._get_active_card(self.team1)
        self.active2 = self._get_active_card(self.team2)

    def _get_active_card(self, team):
        for card in team:
            if card.is_alive():
                return card
        return None

    def get_state(self) -> str:
        """Возвращает строку текущего состояния боя."""
        lines = []
        lines.append("🔴 КОМАНДА 1:")
        for i, card in enumerate(self.team1, 1):
            marker = "👉 " if card == self.active1 else "   "
            lines.append(f"{marker}{i}. {card.get_stats_string()}")
        lines.append("\n🔵 КОМАНДА 2:")
        for i, card in enumerate(self.team2, 1):
            marker = "👉 " if card == self.active2 else "   "
            lines.append(f"{marker}{i}. {card.get_stats_string()}")
        lines.append(f"\nХод: {self.turn+1}")
        if self.last_action_message:
            lines.append(self.last_action_message)
        return "\n".join(lines)

    def get_available_actions(self) -> List[str]:
        """Для командного боя действия всегда доступны, если бой не завершён."""
        if self.finished:
            return []
        return ['attack', 'defend']

    def player_action(self, action: str) -> Tuple[bool, str]:
        """Ход игрока (команда 1). Возвращает (завершён?, сообщение)."""
        if self.finished:
            return True, "Бой уже закончен."

        # Определяем текущую команду
        current_team = 1 if (self.turn % 2 == 0 and self.first_team == 1) or (self.turn % 2 == 1 and self.first_team == 2) else 2

        if current_team == 1:
            actor = self.active1
            target = self.active2
            is_player_turn = True
        else:
            actor = self.active2
            target = self.active1
            is_player_turn = False

        if is_player_turn:
            msg = self._process_turn(actor, target, action)
        else:
            # AI врага
            enemy_action = self._enemy_ai(actor, target)
            msg = self._process_turn(actor, target, enemy_action)

        # Проверка смерти цели
        if not target.is_alive():
            msg += f"\n💀 {target.name} повержен!"
            if current_team == 1:
                self.active2 = self._next_card(self.team2)
            else:
                self.active1 = self._next_card(self.team1)

            if not self.active1 or not self.active2:
                self.finished = True
                self.winner = "КОМАНДА 1" if self.active1 else "КОМАНДА 2"
                return True, msg

        # Сброс эффектов у актора
        self._apply_end_of_turn(actor)

        self.turn += 1
        return self.finished, msg

    def _process_turn(self, actor: BattleCard, target: BattleCard, action: str) -> str:
        if actor.stun:
            actor.clear_stun()
            return f"⏭️ {actor.name} ОГЛУШЕН и пропускает ход!"

        if action == 'attack':
            damage, crit = self._calc_critical(actor.atk)
            stun_occurred = random.random() < 0.1
            if stun_occurred:
                target.apply_stun()
            final_damage = target.take_damage(damage)
            crit_msg = " 💥КРИТИЧЕСКИЙ!💥" if crit else ""
            stun_msg = " и ОГЛУШЕН!" if stun_occurred else ""
            return f"⚔️ {actor.name} наносит {final_damage} урона{crit_msg} {target.name}{stun_msg}"
        elif action == 'defend':
            actor.set_def_bonus()
            return f"🛡️ {actor.name} использует защиту (+{actor.def_bonus} к защите)"
        return "Неизвестное действие"

    def _enemy_ai(self, actor: BattleCard, target: BattleCard) -> str:
        if actor.hp < actor.max_hp * 0.5 and target.atk > actor.atk:
            return 'defend'
        else:
            return 'attack'

    def _next_card(self, team):
        while team and not team[0].is_alive():
            team.pop(0)
        return team[0] if team else None

    def _apply_end_of_turn(self, card):
        card.reset_def_bonus()
        if card.stun:
            card.clear_stun()

    @staticmethod
    def _calc_critical(damage):
        if random.random() < 0.1:
            return damage * 2, True
        return damage, False