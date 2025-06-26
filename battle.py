import random
from data import db
from tinydb import Query

class Player:
    def __init__(self, user_id, cls="warrior", race="human", hp=100, level=1):
        self.user_id = user_id
        self.cls = cls
        self.race = race
        self.hp = hp
        self.level = level

    def to_dict(self):
        return {
            'id': self.user_id,
            'cls': self.cls,
            'race': self.race,
            'hp': self.hp,
            'level': self.level
        }

    @staticmethod
    def from_dict(data):
        return Player(
            user_id=data['id'],
            cls=data.get('cls', 'warrior'),
            race=data.get('race', 'human'),
            hp=data.get('hp', 100),
            level=data.get('level', 1)
        )

class Enemy:
    def __init__(self, name, hp):
        self.name = name
        self.hp = hp


# === Loot ===
loot_table = {
    "1": ["Зелье", "Малый меч"],
    "2": ["Средний меч", "Щит"],
    "3": ["Большой меч", "Артефакт"]
}

def get_loot(tier):
    return random.choice(loot_table[str(tier)])


# === Игроки ===
def get_player(user_id):
    result = db.search(Query().id == user_id)
    if result:
        return Player.from_dict(result[0])
    else:
        player = Player(user_id)
        db.insert(player.to_dict())
        return player

def save_player(player):
    db.upsert(player.to_dict(), Query().id == player.user_id)

# === Генерация врага ===
def generate_enemy(level):
    hp = random.randint(30, 50) + level * 10
    return Enemy("Гоблин", hp)