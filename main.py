from data import *
import telebot, os, pickle
from telebot import types
from tinydb import TinyDB, Query

db=TinyDB('./database/db.json')



predlojka_bot = telebot.TeleBot(TOKEN)
print("predlojka.py in Предложка Империи succesfully started")
q=types.ReplyKeyboardRemove()



def none_type(object):                                      # функция, проверяющая на "нон" тип
	return "" if object==None else f'{object}'


#-------------------------------------------------------------------------------------------------------------------------------------------------------
# bank.py




def edit_currency_info(message, a, b):                  # изменяет в файле значения рублей и батов

	currency_info=[]

	currency_info.append(a)
	currency_info.append(b)
	
	with open("currency_info.pickle", "wb") as file:
		pickle.dump(currency_info, file)
	
	predlojka_bot.reply_to(message, "Данные изменены")


def view_currency_info():

	with open("currency_info.pickle", "rb") as file:
		currency_info = pickle.load(file)
	

	exchange_rate = currency_info[0] / currency_info[1]
    
    
	return (f"{exchange_rate} Имперских батов равняются 1 рублю") # X bats equals 1 ruble



def get_money(message, amount):
	try:
		to_user_id=int(message.text)

		if db.contains(Query().id == to_user_id):

			new_balance=(db.get(Query().id == to_user_id)['balance']+amount)
			new_sender_balance=db.get(Query().id == message.from_user.id)['balance']-amount

			total_amount=new_balance - (new_balance*commission)

			db.update({"balance": new_balance}, Query().id == to_user_id)
			db.update({"balance": new_sender_balance}, Query().id == message.from_user.id)

			predlojka_bot.reply_to(message, "Перевод совершён!")


			predlojka_bot.send_message(to_user_id, "Вам поступил перевод! Проверьте свой баланс: /bank")

		else:
			predlojka_bot.reply_to(message, "У этого id не обнаружено банковского аккаунта")
			  
	except:
		predlojka_bot.reply_to(message, "Это не id, попробуйте с самого начала")




def send_money(message):
	
	try:
		amount=int(message.text)
		sender_balance=db.get(Query().id == message.from_user.id)['balance']
		

		if sender_balance >= amount:
			predlojka_bot.reply_to(message, "Хорошо, а теперь, введите id получателя")
			predlojka_bot.register_next_step_handler(message, get_money, amount)
		

		elif sender_balance < amount:
			predlojka_bot.reply_to(message, "Не достаточно средств")


		else:
			predlojka_bot.reply_to(message, "error")


	except:
		predlojka_bot.reply_to(message, "Это не число, попробуйте с самого начала")




def bank_get_balance(message):
	return db.get(Query().id == message.from_user.id)['balance']


#-------------------------------------------------------------------------------------------------------------------------------------------------------


@predlojka_bot.message_handler(commands=['start'])
def start(message):

	if db.contains(Query().id == message.from_user.id):
		predlojka_bot.reply_to(message, text="С возвращением в Предложку! Ожидаем постов)")

	else:
		db.insert({'id': message.from_user.id, 'name': f'{message.from_user.first_name}', 'last_name': f'{message.from_user.last_name}', 'balance': 0})
		predlojka_bot.reply_to(message, text="Добро пожаловать в Империю!")








@predlojka_bot.message_handler(commands=['edit_currency'])               #обработка команды для изменения курса валют
def editing_currency(message):
	if message.chat.id == admin:
		predlojka_bot.reply_to(message, "Скинь циферки, баты и рубли через запятую")
		predlojka_bot.register_next_step_handler(message, editing_currency2)
	else:
		predlojka_bot.reply_to(message, "Экономику не ломай")







def editing_currency2(message): # функция - посредник, обрабатывает циферки
	try:
		purumpurum=message.text.split(",")

		a=int(purumpurum[0])

		b=int(purumpurum[1])

		edit_currency_info(message, a, b)
	except:
		predlojka_bot.reply_to(message, "Не вышло")







@predlojka_bot.message_handler(commands=['bank'])           # команда "входа" в банк
def bank_meetings(message):    
    reply_button=types.ReplyKeyboardMarkup(row_width=2)
    btn1=types.KeyboardButton("💰Узнать баланс")
    btn2=types.KeyboardButton("🔁Перевод")
    btn3=types.KeyboardButton("📈Курс валюты")
    btn4=types.KeyboardButton("❔Помощь")

    reply_button.add(btn1, btn2, btn3, btn4)

    predlojka_bot.send_message(message.chat.id, "Здравствуйте! Добро пожаловать в Имперский банк! Чтобы вы хотели сделать?", reply_markup=reply_button)

    
    predlojka_bot.register_next_step_handler(message, what_do_you_want_from_bank)








def what_do_you_want_from_bank(message):        # команда, ожижающая callback from user

	
	if message.text == "💰Узнать баланс":
		predlojka_bot.reply_to(message, f"Ваш баланс: {bank_get_balance(message)} Имперских Батов\nВаш id: `{message.from_user.id}`", reply_markup=q, parse_mode='MarkdownV2')


	elif message.text == "🔁Перевод":
		predlojka_bot.reply_to(message, "Введите сумму перевода!", reply_markup=q)
		predlojka_bot.register_next_step_handler(message, send_money)


	elif message.text == "📈Курс валюты":
		predlojka_bot.reply_to(message, f"{view_currency_info()}", reply_markup=q)


	elif message.text == "❔Помощь":
		predlojka_bot.reply_to(message, """
💳 *Функции банка*:  
\- Проверка баланса 
\- Переводы средств \(комиссия 2%\)  
\- Узнавайте курс имперских батов к рублям

📈 *О курсе валют*:  
Курс рассчитывается как общее число батов\, делённое на количество рублей, на которых подкреплена валюта  

🎉 *Бонусы*:  
За каждый одобренный пост вам начисляются баты\, их количество зависит от объёма текста в посте 

📥 Всё просто и удобно\!
						 """, parse_mode="MarkdownV2", reply_markup=q)


	else:
		predlojka_bot.reply_to(message, "Боюсь, я так не умею...", reply_markup=q)
	


@predlojka_bot.message_handler(commands=['help'])
def help(message):
	predlojka_bot.reply_to(message, text="А чё тебе помогать, сам разберёшься", parse_mode='MarkdownV2')











@predlojka_bot.message_handler(content_types=['sticker', 'video', 'photo', 'text', 'document', 'audio', 'voice'])
def accepter(message):
	if message.chat.id != channel and message.chat.id != channel_red and message.chat.id != -1002228334833:
		markup = types.InlineKeyboardMarkup()
		user_name=f'\n\n👤 {message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name != None else ""}'
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
			predlojka_bot.send_video(admin, message.video.file_id, reply_markup=markup, caption = none_type(message.caption) + user_name)
		
		elif message.content_type == 'photo':
			predlojka_bot.send_photo(admin, message.photo[0].file_id, reply_markup=markup, caption = none_type(message.caption) + user_name)
		
		elif message.content_type == 'document':
			predlojka_bot.send_document(admin, message.document.file_id, reply_markup=markup, caption = none_type(message.caption) + user_name)

		elif message.content_type == 'audio':
			predlojka_bot.send_audio(admin, message.audio.file_id, reply_markup=markup, caption = none_type(message.caption) + user_name)

		elif message.content_type == 'voice':
			predlojka_bot.send_voice(admin, message.voice.file_id, reply_markup=markup, caption = none_type(message.caption) + user_name)









@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("+"))
def sender(call):
	predlojka_bot.copy_message(channel, admin, call.message.id)
	predlojka_bot.delete_message(admin, call.message.id)
	print("post was accepted")




@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("&"))
def st_sender(call):
	predlojka_bot.copy_message(channel, admin, call.message.id)
	predlojka_bot.send_message(channel, call.data[1:], disable_notification=True)
	predlojka_bot.delete_message(admin, call.message.id)
	print("sticker was accepted")





@predlojka_bot.callback_query_handler(func=lambda call: (call.data).startswith("-"))
def denier(call):
	predlojka_bot.delete_message(admin, message_id=call.message.id)
	print("post was rejected")


predlojka_bot.infinity_polling()