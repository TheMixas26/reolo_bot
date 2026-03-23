class BattleCard:
    """Класс для карты в бою (хранит состояние и эффекты)"""

    def __init__(self, card_data: dict):
        self.id = card_data.get("id")
        self.name = card_data.get("name")
        self.rarity = card_data.get("rarity")
        self.type = card_data.get("type")
        self.category = card_data.get("category")
        self.ability = card_data.get("ability")

        self.max_hp = card_data.get("hp")
        self.hp = self.max_hp
        self.atk = card_data.get("atk")
        self.defense = card_data.get("def")

        self.def_bonus = 0
        self.stun = False
        self.just_stunned = False

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, damage):
        effective_def = self.defense + self.def_bonus
        final_damage = int(damage * (100 / (100 + effective_def)))
        self.hp -= final_damage
        return final_damage

    def set_def_bonus(self, bonus_percent=0.5):
        self.def_bonus = int(self.defense * bonus_percent)

    def reset_def_bonus(self):
        self.def_bonus = 0

    def apply_stun(self):
        if not self.just_stunned:
            self.stun = True
            self.just_stunned = True

    def clear_stun(self):
        self.stun = False
        self.just_stunned = False

    def get_stats_string(self):
        status = ""
        if self.stun:
            status += " [ОГЛУШЕН]"
        if self.def_bonus > 0:
            status += f" [ЗАЩИТА +{self.def_bonus}]"
        return f"{self.name} ❤️ {self.hp}/{self.max_hp} ⚔️ {self.atk} 🛡️ {self.defense}{status}"

    def __repr__(self):
        return self.get_stats_string()