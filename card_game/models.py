"""Игровые модели карточной системы."""

from __future__ import annotations


class BattleCard:
    """Состояние карты во время боя."""

    def __init__(self, card_data: dict):
        self.id = int(card_data.get("id", 0))
        self.instance_id = str(card_data.get("instance_id", self.id))
        self.name = card_data.get("name")
        self.rarity = card_data.get("rarity")
        self.type = card_data.get("type")
        self.category = card_data.get("category")
        self.ability = card_data.get("ability")

        self.max_hp = int(card_data.get("hp", 0))
        self.hp = self.max_hp
        self.atk = int(card_data.get("atk", 0))
        self.defense = int(card_data.get("def", 0))

        self.def_bonus = 0
        self.stun = False

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, damage: int) -> int:
        effective_def = self.defense + self.def_bonus
        reduced_damage = int(damage * (100 / (100 + effective_def)))
        final_damage = max(1, reduced_damage)
        self.hp = max(0, self.hp - final_damage)
        self.def_bonus = 0
        return final_damage

    def set_def_bonus(self, bonus_percent: float = 0.5) -> None:
        self.def_bonus = max(1, int(self.defense * bonus_percent))

    def apply_stun(self) -> None:
        self.stun = True

    def consume_stun(self) -> bool:
        if not self.stun:
            return False
        self.stun = False
        return True

    def get_stats_string(self) -> str:
        status = []
        if self.stun:
            status.append("ОГЛУШЕН")
        if self.def_bonus > 0:
            status.append(f"ЗАЩИТА +{self.def_bonus}")
        suffix = f" [{' | '.join(status)}]" if status else ""
        return f"{self.name} ❤️ {self.hp}/{self.max_hp} ⚔️ {self.atk} 🛡️ {self.defense}{suffix}"

    def __repr__(self) -> str:
        return self.get_stats_string()
