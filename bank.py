import pickle
from config import predlojka_bot, commission
from database.sqlite_db import user_exists, get_balance, set_balance


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

		if user_exists(to_user_id):

			new_balance=(get_balance(to_user_id)+amount)
			new_sender_balance=get_balance(message.from_user.id)-amount

			total_amount=new_balance - (new_balance*commission)

			set_balance(to_user_id, total_amount)
			set_balance(message.from_user.id, new_sender_balance)

			predlojka_bot.reply_to(message, "Перевод совершён!")


			predlojka_bot.send_message(to_user_id, "Вам поступил перевод! Проверьте свой баланс: /bank")

		else:
			predlojka_bot.reply_to(message, "У этого id не обнаружено банковского аккаунта")
			  
	except:
		predlojka_bot.reply_to(message, "Это не id, попробуйте с самого начала")




def send_money(message):
	
	try:
		amount=int(message.text)
		sender_balance=get_balance(message.from_user.id)
		

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
	return get_balance(message.from_user.id)