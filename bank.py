import pickle
from main import *

with open("rate.pickle", "rb") as file:
	exchange_rate = pickle.load(file)


def edit_currency_info(message):

	currency_info=message.split(",")
	
	with open("currency_info.pickle", "wb") as file:
		pickle.dump(currency_info, file)
	
	predlojka_bot.reply_to(message, "Данные изменены")


def calculate_exchange_rate():

	with open("currency_info.pickle", "rb") as file:
		currency_info = pickle.load(file)
	

	exchange_rate = currency_info[0] / currency_info[1]
    
    
	return (exchange_rate) # X bats equals 1 ruble


def send_money(message, mes_before):
	
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