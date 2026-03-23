import random
from telebot import types
from config import rpg_bot
from database.sqlite_db import get_all_cards, get_inventory, add_to_inventory, roll_card, get_card_by_id
from imp_cards.battle import DuelSession, TeamBattleSession
from imp_cards.game_manager import start_duel, start_team_battle, get_session, end_session

user_temp = {}

@rpg_bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    # Просто приветствие
    rpg_bot.reply_to(message, "Добро пожаловать в карточную игру! Используйте /help для списка команд.")

@rpg_bot.message_handler(commands=['help'])
def help_command(message):
    text = (
        "🎮 <b>Доступные команды:</b>\n"
        "/roll — получить случайную карту\n"
        "/inventory — показать ваши карты\n"
        "/cards — список всех доступных карт\n"
        "/duel — начать дуэль 1 на 1\n"
        "/team_battle — начать командный бой 5 на 5\n"
        "/cancel — отменить текущее действие"
    )
    rpg_bot.send_message(message.chat.id, text, parse_mode="HTML")

@rpg_bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    user_temp.pop(user_id, None)
    end_session(user_id)
    rpg_bot.reply_to(message, "Действие отменено.")

@rpg_bot.message_handler(commands=['roll'])
def roll_command(message):
    user_id = message.from_user.id
    card = roll_card(user_id)
    rpg_bot.reply_to(message, f"🎴 Вы получили карту: <i>{card['name']}</i> ({card['rarity']})", parse_mode="HTML")

@rpg_bot.message_handler(commands=['inventory'])
def inventory_command(message):
    user_id = message.from_user.id
    inv = get_inventory(user_id)
    if not inv:
        rpg_bot.reply_to(message, "Ваш инвентарь пуст. Используйте /roll, чтобы получить карты.")
        return
    text = "🎒 <b>Ваш инвентарь:</b>\n"
    for card in inv:
        text += f"• {card['name']} x{card['amount']} ({card['rarity']}) — ❤️{card['hp']} ⚔️{card['atk']} 🛡️{card['def']}\n"
    rpg_bot.send_message(message.chat.id, text, parse_mode="HTML")

@rpg_bot.message_handler(commands=['cards'])
def cards_command(message):
    cards = get_all_cards()
    text = "📖 <b>Все доступные карты:</b>\n"
    for card in cards:
        text += f"{card['id']}. {card['name']} ({card['rarity']}) — ❤️{card['hp']} ⚔️{card['atk']} 🛡️{card['def']}\n"
    rpg_bot.send_message(message.chat.id, text, parse_mode="HTML")

@rpg_bot.message_handler(commands=['duel'])
def duel_command(message):
    user_id = message.from_user.id
    inv = get_inventory(user_id)
    if not inv:
        rpg_bot.reply_to(message, "У вас нет карт для дуэли. Получите карты через /roll.")
        return

    # Начинаем выбор карты игрока
    markup = types.InlineKeyboardMarkup()
    for card in inv:
        markup.add(types.InlineKeyboardButton(f"{card['name']} ({card['rarity']})", callback_data=f"duel_select_player_{card['id']}"))
    markup.add(types.InlineKeyboardButton("Отмена", callback_data="duel_cancel"))
    rpg_bot.send_message(message.chat.id, "Выберите карту для дуэли:", reply_markup=markup)
    user_temp[user_id] = {"mode": "duel", "step": "select_player_card"}

@rpg_bot.message_handler(commands=['team_battle'])
def team_battle_command(message):
    user_id = message.from_user.id
    inv = get_inventory(user_id)
    if len(inv) < 5:
        rpg_bot.reply_to(message, f"Для командного боя нужно минимум 5 карт. У вас только {len(inv)}. Получите больше через /roll.")
        return

    # Начинаем выбор команды (5 карт)
    user_temp[user_id] = {"mode": "team", "step": "select_team", "selected": []}
    show_team_selection(message, user_id)

def show_team_selection(message, user_id):
    inv = get_inventory(user_id)
    temp = user_temp.get(user_id)
    selected_ids = [c['id'] for c in temp['selected']]
    available = [c for c in inv if c['id'] not in selected_ids]

    if not available:
        # Все карты выбраны, переходим к выбору противника
        choose_opponent_team(message, user_id)
        return

    markup = types.InlineKeyboardMarkup()
    for card in available:
        markup.add(types.InlineKeyboardButton(f"{card['name']} ({card['rarity']})", callback_data=f"team_select_{card['id']}"))
    markup.add(types.InlineKeyboardButton("Готово", callback_data="team_ready"))
    markup.add(types.InlineKeyboardButton("Отмена", callback_data="team_cancel"))
    rpg_bot.edit_message_text(
        f"Выберите карту для команды ({5 - len(temp['selected'])} осталось):\nТекущий состав: {', '.join(c['name'] for c in temp['selected'])}",
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup
    )

def choose_opponent_team(message, user_id):
    # Для простоты противник — случайный набор из 5 карт (можно сделать фиксированный состав)
    all_cards = get_all_cards()
    if len(all_cards) < 5:
        rpg_bot.send_message(message.chat.id, "Недостаточно карт для формирования команды противника.")
        user_temp.pop(user_id, None)
        return
    opponent_team = random.sample(all_cards, 5)
    user_temp[user_id]['opponent'] = opponent_team
    user_temp[user_id]['step'] = 'confirm_team'

    text = "Ваша команда:\n" + "\n".join(f"• {c['name']} ({c['rarity']})" for c in user_temp[user_id]['selected'])
    text += "\n\nКоманда противника:\n" + "\n".join(f"• {c['name']} ({c['rarity']})" for c in opponent_team)
    text += "\n\nНачать бой?"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Начать бой!", callback_data="team_start_battle"))
    markup.add(types.InlineKeyboardButton("Отмена", callback_data="team_cancel"))
    rpg_bot.send_message(message.chat.id, text, reply_markup=markup)

@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith('duel_select_player_'))
def duel_select_player_card(call):
    user_id = call.from_user.id
    if user_temp.get(user_id, {}).get('mode') != 'duel':
        rpg_bot.answer_callback_query(call.id, "Действие неактивно.")
        return

    card_id = int(call.data.split('_')[-1])
    inv = get_inventory(user_id)
    player_card = next((c for c in inv if c['id'] == card_id), None)
    if not player_card:
        rpg_bot.answer_callback_query(call.id, "Карта не найдена.")
        return

    user_temp[user_id]['player_card'] = player_card
    user_temp[user_id]['step'] = 'select_enemy'

    # Предлагаем выбрать противника (все карты или случайный)
    all_cards = get_all_cards()
    markup = types.InlineKeyboardMarkup()
    for card in all_cards:
        markup.add(types.InlineKeyboardButton(f"{card['name']} ({card['rarity']})", callback_data=f"duel_select_enemy_{card['id']}"))
    markup.add(types.InlineKeyboardButton("Случайный", callback_data="duel_random_enemy"))
    markup.add(types.InlineKeyboardButton("Отмена", callback_data="duel_cancel"))
    rpg_bot.edit_message_text(
        "Выберите противника:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )

@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith('duel_select_enemy_'))
def duel_select_enemy_card(call):
    user_id = call.from_user.id
    temp = user_temp.get(user_id)
    if not temp or temp.get('mode') != 'duel' or temp.get('step') != 'select_enemy':
        rpg_bot.answer_callback_query(call.id, "Действие неактивно.")
        return

    card_id = int(call.data.split('_')[-1])
    enemy_card = get_card_by_id(card_id)
    if not enemy_card:
        rpg_bot.answer_callback_query(call.id, "Карта не найдена.")
        return
    start_duel_session(call, user_id, temp['player_card'], enemy_card)

@rpg_bot.callback_query_handler(func=lambda call: call.data == "duel_random_enemy")
def duel_random_enemy(call):
    user_id = call.from_user.id
    temp = user_temp.get(user_id)
    if not temp or temp.get('mode') != 'duel' or temp.get('step') != 'select_enemy':
        rpg_bot.answer_callback_query(call.id, "Действие неактивно.")
        return
    all_cards = get_all_cards()
    enemy_card = random.choice(all_cards)
    start_duel_session(call, user_id, temp['player_card'], enemy_card)

def start_duel_session(call, user_id, player_card, enemy_card):
    session = start_duel(user_id, player_card, enemy_card)
    markup = types.InlineKeyboardMarkup()
    for action in session.get_available_actions():
        markup.add(types.InlineKeyboardButton(action.capitalize(), callback_data=f"duel_action_{action}"))
    text = f"⚔️ Дуэль началась!\n\n{session.get_state()}"
    rpg_bot.edit_message_text(
        text,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )
    user_temp.pop(user_id, None)

@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith('duel_action_'))
def duel_action(call):
    user_id = call.from_user.id
    session = get_session(user_id)
    if not session or not isinstance(session, DuelSession):
        rpg_bot.answer_callback_query(call.id, "Нет активной дуэли.")
        return

    action = call.data.split('_')[-1]
    if action not in session.get_available_actions():
        rpg_bot.answer_callback_query(call.id, "Это действие сейчас недоступно.")
        return

    finished, msg = session.player_action(action)
    if finished:
        rpg_bot.edit_message_text(
            msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        end_session(user_id)
    else:
        markup = types.InlineKeyboardMarkup()
        for a in session.get_available_actions():
            markup.add(types.InlineKeyboardButton(a.capitalize(), callback_data=f"duel_action_{a}"))
        rpg_bot.edit_message_text(
            msg + "\n\n" + session.get_state(),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith('team_select_'))
def team_select_card(call):
    user_id = call.from_user.id
    temp = user_temp.get(user_id)
    if not temp or temp.get('mode') != 'team' or temp.get('step') != 'select_team':
        rpg_bot.answer_callback_query(call.id, "Действие неактивно.")
        return
    card_id = int(call.data.split('_')[-1])
    inv = get_inventory(user_id)
    card = next((c for c in inv if c['id'] == card_id), None)
    if not card:
        rpg_bot.answer_callback_query(call.id, "Карта не найдена.")
        return
    temp['selected'].append(card)
    show_team_selection(call.message, user_id)

@rpg_bot.callback_query_handler(func=lambda call: call.data == "team_ready")
def team_ready(call):
    user_id = call.from_user.id
    temp = user_temp.get(user_id)
    if not temp or temp.get('mode') != 'team' or temp.get('step') != 'select_team':
        rpg_bot.answer_callback_query(call.id, "Действие неактивно.")
        return
    if len(temp['selected']) != 5:
        rpg_bot.answer_callback_query(call.id, "Нужно выбрать ровно 5 карт.")
        return
    choose_opponent_team(call.message, user_id)

@rpg_bot.callback_query_handler(func=lambda call: call.data == "team_start_battle")
def team_start_battle(call):
    user_id = call.from_user.id
    temp = user_temp.get(user_id)
    if not temp or temp.get('mode') != 'team' or temp.get('step') != 'confirm_team':
        rpg_bot.answer_callback_query(call.id, "Действие неактивно.")
        return
    team1 = temp['selected']
    team2 = temp['opponent']
    session = start_team_battle(user_id, team1, team2)

    markup = types.InlineKeyboardMarkup()
    for action in session.get_available_actions():
        markup.add(types.InlineKeyboardButton(action.capitalize(), callback_data=f"team_action_{action}"))
    rpg_bot.edit_message_text(
        f"⚔️ Командный бой начался!\n\n{session.get_state()}",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )
    user_temp.pop(user_id, None)

@rpg_bot.callback_query_handler(func=lambda call: call.data.startswith('team_action_'))
def team_action(call):
    user_id = call.from_user.id
    session = get_session(user_id)
    if not session or not isinstance(session, TeamBattleSession):
        rpg_bot.answer_callback_query(call.id, "Нет активного командного боя.")
        return

    action = call.data.split('_')[-1]
    if action not in session.get_available_actions():
        rpg_bot.answer_callback_query(call.id, "Это действие сейчас недоступно.")
        return

    finished, msg = session.player_action(action)
    if finished:
        rpg_bot.edit_message_text(
            msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        end_session(user_id)
    else:
        markup = types.InlineKeyboardMarkup()
        for a in session.get_available_actions():
            markup.add(types.InlineKeyboardButton(a.capitalize(), callback_data=f"team_action_{a}"))
        rpg_bot.edit_message_text(
            msg + "\n\n" + session.get_state(),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

@rpg_bot.callback_query_handler(func=lambda call: call.data in ("duel_cancel", "team_cancel"))
def cancel_choice(call):
    user_id = call.from_user.id
    user_temp.pop(user_id, None)
    rpg_bot.edit_message_text(
        "Действие отменено.",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )