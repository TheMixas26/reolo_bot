from config import rpg_bot, db
from telebot import types
from tinydb import Query
from battle import generate_enemy, get_loot, get_player, save_player, attack

active_enemies = {}


@rpg_bot.message_handler(commands=['start'])
def hello_from_rpg_bot(message):
    if db.contains(Query().id == message.from_user.id):
        rpg_bot.reply_to(message, text="С возвращением, путник!")
    else:
        db.insert({
            'id': message.from_user.id,
            'name': f'{message.from_user.first_name}',
            'last_name': f'{message.from_user.last_name}',
            'balance': 0
        })
        rpg_bot.reply_to(message, text="Добро пожаловать в RPG!")



@rpg_bot.message_handler(commands=['battle'])
def battle_command(message):
    user_id = message.from_user.id
    player = get_player(user_id)
    enemy = generate_enemy(player.level)
    active_enemies[user_id] = enemy

    markup = types.InlineKeyboardMarkup()
    attack_btn = types.InlineKeyboardButton("Атаковать", callback_data="attack")
    markup.add(attack_btn)

    rpg_bot.send_message(
        message.chat.id,
        f"⚔️ Битва началась!\nПротивник: {enemy.name}, HP: {enemy.hp}\nВаши HP: {player.hp}",
        reply_markup=markup
    )

@rpg_bot.callback_query_handler(func=lambda call: call.data == "attack")
def handle_attack(call):
    try:
        user_id = call.from_user.id
        player = get_player(user_id)
        enemy = active_enemies.get(user_id)
        if not enemy:
            rpg_bot.answer_callback_query(call.id, "Нет активной битвы.")
            return

        damage, dodged, crit = attack(player, enemy)
        log = ""
        if dodged:
            log += f"Вы промахнулись! {enemy.name} уклонился.\n"
        else:
            log += f"Вы нанесли {enemy.name} {damage} урона{' (КРИТ!)' if crit else ''}. У врага осталось {max(enemy.hp, 0)} HP.\n"

        if enemy.hp <= 0:
            log += f"Вы победили {enemy.name}! 🏆\n"
            loot = get_loot(1)
            if loot:
                player.inventory.append(loot)
                log += f"Вы нашли: {loot}\n"
                # Выдача предмета игрока, когда будет реализовано, important!!!
            else:
                log += "Вы не нашли ничего ценного.\n"
            player.level += 1
            player.hp = player.max_hp
            save_player(player)
            active_enemies.pop(user_id, None)
            rpg_bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=log
            )
            return

        edmg, edodged, ecrit = attack(enemy, player)
        if edodged:
            log += f"{enemy.name} промахнулся! Вы уклонились.\n"
        else:
            log += f"{enemy.name} ударил вас на {edmg}{' (КРИТ!)' if ecrit else ''}. У вас осталось {max(player.hp, 0)} HP.\n"

        if player.hp <= 0:
            log += "\nВы проиграли... 💀"
            player.hp = player.max_hp
            active_enemies.pop(user_id, None)
            save_player(player)
            rpg_bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=log
            )
            return

        markup = types.InlineKeyboardMarkup()
        attack_btn = types.InlineKeyboardButton("Атаковать", callback_data="attack")
        markup.add(attack_btn)
        save_player(player)
        rpg_bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=log,
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка в handle_attack: {e}")

@rpg_bot.message_handler(commands=['stats'])
def show_stats(message):
    user_id = message.from_user.id
    player = get_player(user_id)
    rpg_bot.send_message(
        message.chat.id,
        f"Ваш класс: {player.cls}\nРаса: {player.race}\nHP: {player.hp}\nУровень: {player.level}"
    )

@rpg_bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    player = get_player(user_id)
    if player.inventory:
        inv = "\n".join(f"• {item}" for item in player.inventory)
        rpg_bot.send_message(message.chat.id, f"🎒 Ваш инвентарь:\n{inv}")
    else:
        rpg_bot.send_message(message.chat.id, "🎒 Ваш инвентарь пуст.")