"""Сессии боёв для карточной игры."""

from __future__ import annotations

import random
from dataclasses import dataclass

from card_game.models import BattleCard

CRIT_CHANCE = 0.1
STUN_CHANCE = 0.1


def _calc_critical(damage: int) -> tuple[int, bool]:
    if random.random() < CRIT_CHANCE:
        return damage * 2, True
    return damage, False


@dataclass
class PlayerSide:
    user_id: int
    name: str


class DuelSession:
    """Дуэль между двумя пользователями."""

    mode = "duel"

    def __init__(
        self,
        player1_id: int,
        player1_name: str,
        player1_card: dict,
        player2_id: int,
        player2_name: str,
        player2_card: dict,
    ):
        self.sides = {
            player1_id: PlayerSide(player1_id, player1_name),
            player2_id: PlayerSide(player2_id, player2_name),
        }
        self.cards = {
            player1_id: BattleCard(player1_card),
            player2_id: BattleCard(player2_card),
        }
        self.participants = (player1_id, player2_id)
        self.current_turn_user_id = random.choice(self.participants)
        self.turn = 1
        self.finished = False
        self.winner_user_id: int | None = None

    def get_participant_ids(self) -> tuple[int, int]:
        return self.participants

    def get_state(self) -> str:
        lines = []
        for user_id in self.participants:
            side = self.sides[user_id]
            card = self.cards[user_id]
            marker = "👉 " if user_id == self.current_turn_user_id and not self.finished else ""
            lines.append(f"{marker}{side.name}: {card.get_stats_string()}")
        if self.finished:
            lines.append("")
            lines.append(self._result_line())
        else:
            lines.append("")
            lines.append(f"Ход: {self.sides[self.current_turn_user_id].name}")
            lines.append(f"Раунд: {self.turn}")
        return "\n".join(lines)

    def get_available_actions(self, user_id: int) -> list[str]:
        if self.finished or user_id != self.current_turn_user_id:
            return []
        return ["attack", "defend"]

    def perform_action(self, user_id: int, action: str) -> tuple[bool, str]:
        if self.finished:
            return True, "Дуэль уже завершена."
        if user_id != self.current_turn_user_id:
            return False, "Сейчас не ваш ход."

        actor = self.cards[user_id]
        target_user_id = self._other_user_id(user_id)
        target = self.cards[target_user_id]
        messages = [self._process_action(actor, target, action)]

        if not target.is_alive():
            self.finished = True
            self.winner_user_id = user_id
            return True, "\n".join(messages + ["", self._result_line()])

        messages.extend(self._advance_turn())
        return self.finished, "\n".join(messages)

    def _advance_turn(self) -> list[str]:
        messages: list[str] = []
        safety = 0
        next_user_id = self._other_user_id(self.current_turn_user_id)

        while safety < len(self.participants):
            actor = self.cards[next_user_id]
            if not actor.consume_stun():
                break
            messages.append(f"⏭️ {self.sides[next_user_id].name} пропускает ход: {actor.name} оглушена.")
            next_user_id = self._other_user_id(next_user_id)
            safety += 1

        self.current_turn_user_id = next_user_id
        self.turn += 1
        return messages

    def _process_action(self, actor: BattleCard, target: BattleCard, action: str) -> str:
        if action == "attack":
            damage, crit = _calc_critical(actor.atk)
            stun_occurred = random.random() < STUN_CHANCE
            if stun_occurred:
                target.apply_stun()
            final_damage = target.take_damage(damage)
            crit_msg = " Критический удар!" if crit else ""
            stun_msg = " Цель оглушена!" if stun_occurred else ""
            return f"⚔️ {actor.name} наносит {final_damage} урона по карте {target.name}.{crit_msg}{stun_msg}"

        actor.set_def_bonus()
        return f"🛡️ {actor.name} усиливает защиту на {actor.def_bonus} до следующего попадания."

    def _other_user_id(self, user_id: int) -> int:
        return self.participants[1] if self.participants[0] == user_id else self.participants[0]

    def _result_line(self) -> str:
        if self.winner_user_id is None:
            return "Бой завершён."
        return f"🏆 Победитель: {self.sides[self.winner_user_id].name}"


class TeamBattleSession:
    """Командный бой между двумя пользователями."""

    mode = "team"

    def __init__(
        self,
        player1_id: int,
        player1_name: str,
        team1_cards: list[dict],
        player2_id: int,
        player2_name: str,
        team2_cards: list[dict],
    ):
        self.sides = {
            player1_id: PlayerSide(player1_id, player1_name),
            player2_id: PlayerSide(player2_id, player2_name),
        }
        self.participants = (player1_id, player2_id)
        self.teams = {
            player1_id: [BattleCard({**card, "instance_id": f"{player1_id}_{index}"}) for index, card in enumerate(team1_cards, start=1)],
            player2_id: [BattleCard({**card, "instance_id": f"{player2_id}_{index}"}) for index, card in enumerate(team2_cards, start=1)],
        }
        self.current_turn_user_id = random.choice(self.participants)
        self.turn = 1
        self.finished = False
        self.winner_user_id: int | None = None
        self.selected_actor_id: str | None = None
        self.stage = "choose_actor"

    def get_participant_ids(self) -> tuple[int, int]:
        return self.participants

    def get_state(self) -> str:
        lines = []
        for user_id in self.participants:
            marker = "👉 " if user_id == self.current_turn_user_id and not self.finished else ""
            lines.append(f"{marker}{self.sides[user_id].name}:")
            for card in self.teams[user_id]:
                selected = " [ВЫБРАНА]" if card.instance_id == self.selected_actor_id else ""
                lines.append(f"• {card.get_stats_string()}{selected}")
            lines.append("")

        if self.finished:
            lines.append(self._result_line())
        else:
            lines.append(f"Ход: {self.sides[self.current_turn_user_id].name}")
            lines.append(f"Раунд: {self.turn}")
            lines.append(f"Этап: {self._stage_label()}")
        return "\n".join(lines).strip()

    def get_available_actions(self, user_id: int) -> list[str]:
        if self.finished or user_id != self.current_turn_user_id or self.stage != "choose_action":
            return []
        return ["attack", "defend"]

    def get_selectable_actors(self, user_id: int) -> list[BattleCard]:
        if self.finished or user_id != self.current_turn_user_id or self.stage != "choose_actor":
            return []
        return [card for card in self.teams[user_id] if card.is_alive()]

    def get_selectable_targets(self, user_id: int) -> list[BattleCard]:
        if self.finished or user_id != self.current_turn_user_id or self.stage != "choose_target":
            return []
        opponent_id = self._other_user_id(user_id)
        return [card for card in self.teams[opponent_id] if card.is_alive()]

    def choose_actor(self, user_id: int, instance_id: str) -> tuple[bool, str | None]:
        if self.finished:
            return True, "Бой уже завершён."
        if user_id != self.current_turn_user_id or self.stage != "choose_actor":
            return False, "Сейчас нельзя выбирать карту."

        actor = self._get_card_by_instance(user_id, instance_id)
        if actor is None or not actor.is_alive():
            return False, "Эта карта сейчас недоступна."

        if actor.consume_stun():
            text = f"⏭️ {actor.name} оглушена и теряет действие."
            self._end_turn()
            return self.finished, text

        self.selected_actor_id = actor.instance_id
        self.stage = "choose_action"
        return False, None

    def choose_action(self, user_id: int, action: str) -> tuple[bool, str | None]:
        if self.finished:
            return True, "Бой уже завершён."
        if user_id != self.current_turn_user_id or self.stage != "choose_action":
            return False, "Сейчас нельзя выбрать это действие."

        actor = self._get_card_by_instance(user_id, self.selected_actor_id)
        if actor is None or not actor.is_alive():
            self._reset_turn_state()
            return False, "Выбранная карта больше недоступна."

        if action == "attack":
            self.stage = "choose_target"
            return False, None

        actor.set_def_bonus()
        text = f"🛡️ {actor.name} усиливает защиту на {actor.def_bonus} до следующего попадания."
        self._end_turn()
        return self.finished, text

    def choose_target(self, user_id: int, target_instance_id: str) -> tuple[bool, str]:
        if self.finished:
            return True, "Бой уже завершён."
        if user_id != self.current_turn_user_id or self.stage != "choose_target":
            return False, "Сейчас нельзя выбрать цель."

        actor = self._get_card_by_instance(user_id, self.selected_actor_id)
        opponent_id = self._other_user_id(user_id)
        target = self._get_card_by_instance(opponent_id, target_instance_id)
        if actor is None or target is None or not actor.is_alive() or not target.is_alive():
            return False, "Атакующая карта или цель уже недоступны."

        damage, crit = _calc_critical(actor.atk)
        stun_occurred = random.random() < STUN_CHANCE
        if stun_occurred:
            target.apply_stun()
        final_damage = target.take_damage(damage)

        crit_msg = " Критический удар!" if crit else ""
        stun_msg = " Цель оглушена!" if stun_occurred else ""
        text = f"⚔️ {actor.name} наносит {final_damage} урона по карте {target.name}.{crit_msg}{stun_msg}"

        if not target.is_alive():
            text += f"\n💀 {target.name} выбывает из боя."
            if not self._has_alive_cards(opponent_id):
                self.finished = True
                self.winner_user_id = user_id
                self._reset_turn_state()
                return True, "\n".join([text, "", self._result_line()])

        self._end_turn()
        return self.finished, text

    def go_back_to_actor_choice(self, user_id: int) -> bool:
        if self.finished or user_id != self.current_turn_user_id:
            return False
        self._reset_turn_state()
        return True

    def _end_turn(self) -> None:
        if self.finished:
            return
        self.current_turn_user_id = self._other_user_id(self.current_turn_user_id)
        self.turn += 1
        self._reset_turn_state()

    def _reset_turn_state(self) -> None:
        self.selected_actor_id = None
        self.stage = "choose_actor"

    def _get_card_by_instance(self, user_id: int, instance_id: str | None) -> BattleCard | None:
        if not instance_id:
            return None
        return next((card for card in self.teams[user_id] if card.instance_id == instance_id), None)

    def _other_user_id(self, user_id: int) -> int:
        return self.participants[1] if self.participants[0] == user_id else self.participants[0]

    def _has_alive_cards(self, user_id: int) -> bool:
        return any(card.is_alive() for card in self.teams[user_id])

    def _stage_label(self) -> str:
        if self.stage == "choose_actor":
            return "выбор карты"
        if self.stage == "choose_action":
            return "выбор действия"
        return "выбор цели"

    def _result_line(self) -> str:
        if self.winner_user_id is None:
            return "Командный бой завершён."
        return f"🏆 Победитель: {self.sides[self.winner_user_id].name}"
