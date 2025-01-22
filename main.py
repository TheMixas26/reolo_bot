from data import *
import telebot
from telebot import types

predlojka_bot = telebot.TeleBot(TOKEN)
# object!="" or object!='None' or object != None or object!=''
print("predlojka.py in Предложка Империи succesfully started")

def none_type(object):
	return "" if object==None else f'{object}'

@predlojka_bot.message_handler(commands=['start'])
def start(message):
	predlojka_bot.reply_to(message, text="Здравствуйте\!\!\! Добро поджаловать в Предложку Империи\!\nПрисылайте сюда всё, что только душе угодно, а я передам админу на рассмотрение\! Если его всё устроит, ваше сообщение будет опубликовано\!\n\n_P\.S\. Анонимки пока нет_", parse_mode='MarkdownV2')
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