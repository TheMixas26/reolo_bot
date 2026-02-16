from config import bank_bot, db
from tinydb import Query
from telebot import types
from bank import view_currency_info, send_money, bank_get_balance


q = types.ReplyKeyboardRemove()


@bank_bot.message_handler(commands=['start'])
def hello_from_bank_bot(message):
    if db.contains(Query().id == message.from_user.id):
        bank_bot.reply_to(message, text="С возвращением в Казначейство!")
    else:
        db.insert({
            'id': message.from_user.id,
            'name': f'{message.from_user.first_name}',
            'last_name': f'{message.from_user.last_name}',
            'balance': 0
        })
        bank_bot.reply_to(message, text="Добро пожаловать в Имперское Казначейство!")




@bank_bot.message_handler(commands=['bank'])
def bank_meetings(message):
    reply_button = types.ReplyKeyboardMarkup(row_width=2)
    btn1 = types.KeyboardButton("💰Узнать баланс")
    btn2 = types.KeyboardButton("🔁Перевод")
    btn3 = types.KeyboardButton("📈Курс валюты")
    btn4 = types.KeyboardButton("❔Помощь")
    reply_button.add(btn1, btn2, btn3, btn4)
    bank_bot.send_message(
        message.chat.id,
        "Здравствуйте! Добро пожаловать в Имперский банк! Чтобы вы хотели сделать?",
        reply_markup=reply_button
    )
    bank_bot.register_next_step_handler(message, what_do_you_want_from_bank)

def what_do_you_want_from_bank(message):
    if message.text == "💰Узнать баланс":
        bank_bot.reply_to(
            message,
            f"Ваш баланс: {bank_get_balance(message)} Имперских Батов\nВаш id: `{message.from_user.id}`",
            reply_markup=q,
            parse_mode='MarkdownV2'
        )
    elif message.text == "🔁Перевод":
        bank_bot.reply_to(message, "Введите сумму перевода!", reply_markup=q)
        bank_bot.register_next_step_handler(message, send_money)
    elif message.text == "📈Курс валюты":
        bank_bot.reply_to(message, f"{view_currency_info()}", reply_markup=q)
    elif message.text == "❔Помощь":
        bank_bot.reply_to(message, r"""
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
        bank_bot.reply_to(message, "Боюсь, я так не умею...", reply_markup=q)


