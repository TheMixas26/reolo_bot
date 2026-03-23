import random
import os

def calc_critical(damage):
    """С вероятностью 10% возвращает удвоенный урон"""
    if random.random() < 0.1:
        return damage * 2, True
    return damage, False

def clear_screen():
    """Очистка консоли"""
    os.system('cls' if os.name == 'nt' else 'clear')

def wait_for_enter():
    """Ожидание нажатия Enter"""
    input("\nНажмите Enter для продолжения...")

def get_player_choice(actions, prompt):
    """Универсальная функция для получения выбора игрока"""
    print(prompt)
    for i, action in enumerate(actions, 1):
        action_display = {
            'attack': '⚔️ Атаковать',
            'defend': '🛡️ Защищаться',
            'skip': '⏭️ Пропустить ход'
        }.get(action, action)
        print(f"{i}. {action_display}")
    
    while True:
        try:
            choice = int(input("Ваш выбор: "))
            if 1 <= choice <= len(actions):
                return actions[choice - 1]
            else:
                print(f"Пожалуйста, выберите число от 1 до {len(actions)}")
        except ValueError:
            print("Пожалуйста, введите число")

def perform_action(actor, action, target=None, verbose=True):
    """Выполняет действие и возвращает сообщение"""
    msg = ""
    if action == 'attack':
        base_damage = actor.atk
        damage, crit = calc_critical(base_damage)
        
        stun_chance = 0.1
        stun_occurred = False
        if random.random() < stun_chance:
            target.apply_stun()
            stun_occurred = True
        
        final_damage = target.take_damage(damage)
        crit_msg = " 💥КРИТИЧЕСКИЙ!💥" if crit else ""
        stun_msg = " и ОГЛУШЕН!" if stun_occurred else ""
        msg = f"⚔️ {actor.name} наносит {final_damage} урона{crit_msg} {target.name}{stun_msg}"
        if verbose:
            print(msg)
    
    elif action == 'defend':
        actor.set_def_bonus()
        msg = f"🛡️ {actor.name} использует защиту (+{actor.def_bonus} к защите)"
        if verbose:
            print(msg)
    
    elif action == 'skip':
        msg = f"⏭️ {actor.name} ОГЛУШЕН и пропускает ход!"
        if verbose:
            print(msg)
    
    return msg

def apply_end_of_turn_effects(card):
    """Сброс временных эффектов в конце хода"""
    card.reset_def_bonus()
    if card.stun:
        card.clear_stun()

def display_cards(cards, title="Доступные карты"):
    """Отображает список карт"""
    print(f"\n{title}:")
    print("-"*60)
    for i, card in enumerate(cards, 1):
        print(f"{i:2}. {card.get('name')} | ❤️ {card.get('hp')} ⚔️ {card.get('atk')} 🛡️ {card.get('def')} | {card.get('rarity')}")
    print("-"*60)