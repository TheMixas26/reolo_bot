from data import predlojka_bot, db, admin, channel, channel_red, bot_version
from telebot import types
from tinydb import Query
from bank import edit_currency_info, view_currency_info, send_money, bank_get_balance
from battle import generate_enemy, get_loot, get_player, save_player
import random

q = types.ReplyKeyboardRemove()
active_enemies = {}

def none_type(object):
    return "" if object is None else f'{object}'

@predlojka_bot.message_handler(commands=['start'])
def start(message):
    if db.contains(Query().id == message.from_user.id):
        predlojka_bot.reply_to(message, text="С возвращением в Предложку! Ожидаем постов)")
    else:
        db.insert({'id': message.from_user.id, 'name': f'{message.from_user.first_name}', 'last_name': f'{message.from_user.last_name}', 'balance': 0})
        predlojka_bot.reply_to(message, text="Добро пожаловать в Империю!")

@predlojka_bot.message_handler(commands=['changelog'])
def changelog(message):
    try:
        with open('changelog.txt', mode='r', encoding='utf-8') as f:
            predlojka_bot.send_document(message.chat.id, f, reply_to_message_id=message.message_id, caption=f"Вот моя история обновлений! Текущая версия - <b>{bot_version}</b>", parse_mode='HTML')
    except Exception as e:
        print(e)
        predlojka_bot.reply_to(message, text="Не удалось загрузить Информацию о последнем обновлении. (X_X)\nТеперь меня снова закроют в подвале и больше никогда не запустят (≧ ﹏ ≦)")

@predlojka_bot.message_handler(commands=['edit_currency'])
def editing_currency(message):
    if message.chat.id == admin:
        predlojka_bot.reply_to(message, "Скинь циферки, баты и рубли через запятую")
        predlojka_bot.register_next_step_handler(message, editing_currency2)
    else:
        predlojka_bot.reply_to(message, "Экономику не ломай")

def editing_currency2(message):
    try:
        purumpurum = message.text.split(",")
        a = int(purumpurum[0])
        b = int(purumpurum[1])
        edit_currency_info(message, a, b)
    except:
        predlojka_bot.reply_to(message, "Не вышло")

@predlojka_bot.message_handler(commands=['bank'])
def bank_meetings(message):
    reply_button = types.ReplyKeyboardMarkup(row_width=2)
    btn1 = types.KeyboardButton("💰Узнать баланс")
    btn2 = types.KeyboardButton("🔁Перевод")
    btn3 = types.KeyboardButton("📈Курс валюты")
    btn4 = types.KeyboardButton("❔Помощь")
    reply_button.add(btn1, btn2, btn3, btn4)
    predlojka_bot.send_message(message.chat.id, "Здравствуйте! Добро пожаловать в Имперский банк! Чтобы вы хотели сделать?", reply_markup=reply_button)
    predlojka_bot.register_next_step_handler(message, what_do_you_want_from_bank)

def what_do_you_want_from_bank(message):
    if message.text == "💰Узнать баланс":
        predlojka_bot.reply_to(message, f"Ваш баланс: {bank_get_balance(message)} Имперских Батов\nВаш id: `{message.from_user.id}`", reply_markup=q, parse_mode='MarkdownV2')
    elif message.text == "🔁Перевод":
        predlojka_bot.reply_to(message, "Введите сумму перевода!", reply_markup=q)
        predlojka_bot.register_next_step_handler(message, send_money)
    elif message.text == "📈Курс валюты":
        predlojka_bot.reply_to(message, f"{view_currency_info()}", reply_markup=q)
    elif message.text == "❔Помощь":
        predlojka_bot.reply_to(message, r"""
💳 *Функции банка*:  
\- Проверка баланса 
\- Переводы средств \(комиссия 2%\)  
\- Узнавайте курс имперских батов к рублям

📈 *О курсе валют*:  
Курс рассчитывается как общее число батов\, делённое на количество рублей, на которых подкреплена валюта  

🎉 *Бонусы*:  
За каждый одобренный пост вам начисляются баты\, их количество зависит от объёма текста в посте (WIP)

📥 Всё просто и удобно\!
        """, parse_mode="MarkdownV2", reply_markup=q)
    else:
        predlojka_bot.reply_to(message, "Боюсь, я так не умею...", reply_markup=q)

@predlojka_bot.message_handler(commands=['help'])
def help(message):
    try:
        with open('help_info.txt', mode='r', encoding='utf-8') as f:
            help_string = f.read()
        predlojka_bot.reply_to(message, text=help_string, parse_mode='HTML')
    except Exception as e:
        print(e)
        predlojka_bot.reply_to(message, text="Не удалось загрузить справку. (X_X)\nТеперь меня снова закроют в подвале и больше никогда не запустят (≧ ﹏ ≦)")

@predlojka_bot.message_handler(commands=['battle'])
def battle_command(message):
    global active_enemies
    active_enemies = {}
    user_id = message.from_user.id
    player = get_player(user_id)
    enemy = generate_enemy(player.level)
    active_enemies[user_id] = enemy
    markup = types.InlineKeyboardMarkup()
    attack_btn = types.InlineKeyboardButton("Атаковать", callback_data="attack")
    markup.add(attack_btn)
    predlojka_bot.send_message(message.chat.id, f"⚔️ Битва началась!\nПротивник: {enemy.name}, HP: {enemy.hp}", reply_markup=markup)

@predlojka_bot.callback_query_handler(func=lambda call: print(call.data) or call.data and call.data.startswith("a"))
def handle_attack(call):
    try:
        print("entering callback handler")
        user_id = call.from_user.id
        player = get_player(user_id)
        enemy = active_enemies.get(user_id)
        if not enemy:
            predlojka_bot.answer_callback_query(call.id, "Нет активной битвы.")
            return
        damage = random.randint(5, 10)
        enemy.hp -= damage
        result = f"Вы ударили {enemy.name} на {damage} урона. У него осталось {max(enemy.hp, 0)} HP.\n"
        if enemy.hp <= 0:
            result += f"Вы победили {enemy.name}! 🏆\n"
            loot = get_loot(1)
            result += f"Вы нашли: {loot}"
            player.level += 1
            player.hp = 100
            save_player(player)
            active_enemies.pop(user_id, None)
            predlojka_bot.send_message(chat_id=call.message.chat.id, text=result)
            return
        edmg = random.randint(3, 8)
        player.hp -= edmg
        result += f"{enemy.name} ударил вас на {edmg}. У вас осталось {max(player.hp, 0)} HP."
        if player.hp <= 0:
            result += "\nВы проиграли... 💀"
            player.hp = 100
            active_enemies.pop(user_id, None)
            save_player(player)
            predlojka_bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=result)
            return
        markup = types.InlineKeyboardMarkup()
        attack_btn = types.InlineKeyboardButton("Атаковать", callback_data="attack")
        markup.add(attack_btn)
        save_player(player)
        predlojka_bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=result, reply_markup=markup)
    except Exception as e:
        print(f"Ошибка в handle_attack: {e}")

@predlojka_bot.message_handler(commands=['stats'])
def show_stats(message):
    user_id = message.from_user.id
    player = get_player(user_id)
    predlojka_bot.send_message(message.chat.id, f"Ваш класс: {player.cls}\nРаса: {player.race}\nHP: {player.hp}\nУровень: {player.level}")

@predlojka_bot.message_handler(content_types=['sticker', 'video', 'photo', 'text', 'document', 'audio', 'voice'])
def accepter(message):
    if message.chat.id != channel and message.chat.id != channel_red and message.chat.id != -1002228334833:
        markup = types.InlineKeyboardMarkup()
        adafa_think_text_content = message.text if message.content_type == 'text' else message.caption or ""
        if '#анон' in adafa_think_text_content.lower():
            user_name = '\n\n🤫 Аноним'
        else:
            user_name = f'\n\n👤 {message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name != None else ""}'
        if '#вопрос' in adafa_think_text_content:
            predlojka_bot.send_message(message.chat.id, f"Спасибо за ваш вопрос, {user_name[4:]}!!!", reply_markup=q)
            markup.add(types.InlineKeyboardButton("Ответить", callback_data="+" + user_name + 'question'+'|'))
            markup.add(types.InlineKeyboardButton("Игнор", callback_data="-"))
            print(f"Predlojka get new message! It is {message.content_type}")
            if message.content_type == 'text':
                predlojka_bot.send_message(admin, f'Вам поступил новый вопрос от {user_name[4:]}\n\n<blockquote>{message.text}</blockquote>', reply_markup=markup, parse_mode='HTML')
            elif message.content_type == 'sticker':
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Ответить", callback_data="&" + user_name + 'question'+'|'))
                markup.add(types.InlineKeyboardButton("Игнор", callback_data="-"))
                predlojka_bot.send_sticker(admin, message.sticker.file_id, reply_markup=markup)
            elif message.content_type == 'video':
                predlojka_bot.send_video(admin, message.video.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'photo':
                predlojka_bot.send_photo(admin, message.photo[0].file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'document':
                predlojka_bot.send_document(admin, message.document.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'audio':
                predlojka_bot.send_audio(admin, message.audio.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'voice':
                predlojka_bot.send_voice(admin, message.voice.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
        else:
            predlojka_bot.send_message(message.chat.id, f"Спасибо за ваше сообщение, {user_name[4:]}!!!", reply_markup=q)
            markup.add(types.InlineKeyboardButton("Одобрить", callback_data="+" + user_name))
            markup.add(types.InlineKeyboardButton("Запретить", callback_data="-"))
            print(f"Predlojka get new message! It is {message.content_type}")
            if message.content_type == 'text':
                predlojka_bot.send_message(admin, message.text + user_name, reply_markup=markup)
            elif message.content_type == 'sticker':
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Одобрить", callback_data="&" + user_name))
                markup.add(types.InlineKeyboardButton("Запретить", callback_data="-"))
                predlojka_bot.send_sticker(admin, message.sticker.file_id, reply_markup=markup)
            elif message.content_type == 'video':
                predlojka_bot.send_video(admin, message.video.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'photo':
                predlojka_bot.send_photo(admin, message.photo[0].file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'document':
                predlojka_bot.send_document(admin, message.document.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'audio':
                predlojka_bot.send_audio(admin, message.audio.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)
            elif message.content_type == 'voice':
                predlojka_bot.send_voice(admin, message.voice.file_id, reply_markup=markup, caption=none_type(message.caption) + user_name)

@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("+"))
def sender(call):
    predlojka_bot.copy_message(channel, admin, call.message.id)
    predlojka_bot.delete_message(admin, call.message.id)
    print("post was accepted")

@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("&"))
def st_sender(call):
    if 'question' not in call.data:
        predlojka_bot.copy_message(channel, admin, call.message.id)
        predlojka_bot.send_message(channel, call.data[1:], disable_notification=True)
        predlojka_bot.delete_message(admin, call.message.id)
        print("sticker was accepted")
    else:
        predlojka_bot.copy_message(channel, admin, call.message.id)
        predlojka_bot.send_message(channel, call.data[1:], disable_notification=True)
        predlojka_bot.delete_message(admin, call.message.id)
        print("sticker-question was accepted")

@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("-"))
def denier(call):
    predlojka_bot.delete_message(admin, message_id=call.message.id)
    print("post was rejected")