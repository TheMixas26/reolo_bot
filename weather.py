import requests
from data import predlojka_bot, chat_mishas_den, admin

def get_weather():
  return weather
  
def send_weather():
  text = f"Дорогие подписчики! Прогноз погоды на сегодня: {get_weather()}"
  predlojka_bot.send_message(chat_mishas_den, text)