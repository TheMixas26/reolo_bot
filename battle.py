import random
from config import db
from tinydb import Query

# --- Классы и расы ---
CLASS_STATS = {
    "warrior": {"atk": 10, "defn": 5, "hp": 100},
    "mage": {"atk": 14, "defn": 2, "hp": 80},
    "rogue": {"atk": 8, "defn": 3, "hp": 90, "dodge": 0.15}
}
RACE_BONUS = {
    "human": {"hp": 0, "atk": 0},
    "elf": {"atk": 2},
    "orc": {"hp": 20}
}

class Player:
    def __init__(self, user_id, cls="warrior", race="human", hp=None, level=1, atk=None, defn=15, dodge=0.09, inventory=None):
        self.user_id = user_id
        self.cls = cls
        self.race = race
        base = CLASS_STATS.get(cls, CLASS_STATS["warrior"]).copy()
        bonus = RACE_BONUS.get(race, {})
        self.max_hp = base["hp"] + bonus.get("hp", 0)
        self.hp = hp if hp is not None else self.max_hp
        self.level = level
        self.atk = atk if atk is not None else base["atk"] + bonus.get("atk", 0)
        self.defn = defn if defn is not None else base.get("defn", 0)
        self.dodge = base.get("dodge", 0.05)  # шанс уклонения
        self.inventory = inventory if inventory is not None else []

    def to_dict(self):
        return {
            'id': self.user_id,
            'cls': self.cls,
            'race': self.race,
            'hp': self.hp,
            'level': self.level,
            'atk': self.atk,
            'defn': self.defn,
            'dodge': self.dodge,
            'inventory': self.inventory
        }

    @staticmethod
    def from_dict(data):
        return Player(
            user_id=data['id'],
            cls=data.get('cls', 'warrior'),
            race=data.get('race', 'human'),
            hp=data.get('hp'),
            level=data.get('level', 1),
            atk=data.get('atk'),
            defn=data.get('defn'),
            dodge=data.get('dodge', 0.05),
            inventory=data.get('inventory', [])
        )

class Enemy:
    def __init__(self, name, hp, atk, defn, dodge=0.02):
        self.name = name
        self.hp = hp
        self.atk = atk
        self.defn = defn
        self.dodge = dodge


# --- Loot ---
loot_table = {
    1: [
        {"name": "Зелье лечения", "chance": 0.4},
        {"name": "Малый меч", "chance": 0.15},
        {"name": "Кусок золота", "chance": 0.3},
        {"name": "Ничего", "chance": 0.15}
    ],
    2: [
        {"name": "Средний меч", "chance": 0.18},
        {"name": "Щит", "chance": 0.18},
        {"name": "Зелье лечения", "chance": 0.25},
        {"name": "Кусок золота", "chance": 0.25},
        {"name": "Ничего", "chance": 0.14}
    ],
    3: [
        {"name": "Большой меч", "chance": 0.15},
        {"name": "Артефакт", "chance": 0.07},
        {"name": "Щит", "chance": 0.18},
        {"name": "Зелье лечения", "chance": 0.2},
        {"name": "Кусок золота", "chance": 0.25},
        {"name": "Ничего", "chance": 0.15}
    ]
}

def get_loot(tier):
    table = loot_table.get(tier, loot_table[1])
    roll = random.random()
    cumulative = 0
    for item in table:
        cumulative += item["chance"]
        if roll < cumulative:
            if item["name"] == "Ничего":
                return None
            return item["name"]
    return None


# --- Игроки ---
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

# --- Генерация врага ---
ENEMY_TYPES = [
    {"name": "Гоблин", "hp": 40, "atk": 7, "defn": 1, "dodge": 0.05},
    {"name": "Орк", "hp": 60, "atk": 10, "defn": 3, "dodge": 0.03},
    {"name": "Скелет", "hp": 35, "atk": 8, "defn": 0, "dodge": 0.10},
    {"name": "Дракон", "hp": 120, "atk": 18, "defn": 7, "dodge": 0.005}
]

def generate_enemy(level):
    etype = random.choice(ENEMY_TYPES)
    hp = etype["hp"] + level * 8
    atk = etype["atk"] + level * 2
    defn = etype["defn"] + level
    dodge = etype["dodge"]
    return Enemy(etype["name"], hp, atk, defn, dodge)

# --- Боевая логика ---
def attack(attacker, defender):
    if random.random() < defender.dodge:
        return 0, True, False
    crit = random.random() < 0.1
    base_damage = attacker.atk - defender.defn * 0.5 + getattr(attacker, "level", 1)
    if crit:
        base_damage += attacker.atk
    spread = random.uniform(0.85, 1.15)
    damage = max(1, int(base_damage * spread))
    defender.hp -= damage
    return damage, False, crit