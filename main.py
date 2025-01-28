from data import *
import telebot, os, pickle
from telebot import types


class user:
	def __init__(self, id, name, surname, balance):
		self.id = id
		self.name = name
		self.surname = surname
		self.balance = balance



predlojka_bot = telebot.TeleBot(TOKEN)
# object!="" or object!='None' or object != None or object!=''
print("predlojka.py in Предложка Империи succesfully started")




def none_type(object):           # функция, проверяющая на "нон" тип
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

def send_money(message):
	
	try:
		amount=int(message.text)
		
		if user.balance >= amount:
				user.balance-=amount
				
				user.balance2+=amount
		elif user.balance < amount:
				predlojka_bot.reply_to_message(message, "not enought")
		else:
				predlojka_bot.reply_to_message(message, "error")
	except:
		predlojka_bot.reply_to_message(message, "not amount")


def bank_get_balance(message):
	print()


#-------------------------------------------------------------------------------------------------------------------------------------------------------


@predlojka_bot.message_handler(commands=['start'])
def start(message):
	if f"{message.chat.id}.pickle" in os.listdir(path='./database'):

		predlojka_bot.reply_to(message, text="Вы есть")

	else:
		predlojka_bot.reply_to(message, text="Вас нет")








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
    btn4=types.KeyboardButton("🚫Оплатить штрафы")

    reply_button.add(btn1, btn2, btn3, btn4)

    predlojka_bot.send_message(message.chat.id, "Здравствуйте! Добро пожаловать в Имперский банк! Чтобы вы хотели сделать?", reply_markup=reply_button)

    
    predlojka_bot.register_next_step_handler(message, what_do_you_want_from_bank)








def what_do_you_want_from_bank(message):        # команда, ожижающая callback from user
	q=types.ReplyKeyboardRemove()
	
	if message.text == "💰Узнать баланс":
		predlojka_bot.reply_to(message, f"Ваш баланс: {bank_get_balance(message)}", reply_markup=q)

	elif message.text == "🔁Перевод":
		print("перевод")

	elif message.text == "📈Курс валюты":
		predlojka_bot.reply_to(message, f"{view_currency_info()}", reply_markup=q)

	elif message.text == "🚫Оплатить штрафы":
		print("штраф detected")

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
		predlojka_bot.send_message(message.chat.id, f"Спасибо за ваше сообщение, {user_name[4:]}!!!")

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