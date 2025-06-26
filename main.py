from data import predlojka_bot
import handlers  # Важно: просто импорт, чтобы зарегистрировать все обработчики

print("predlojka.py in Предложка Империи succesfully started")

if __name__ == "__main__":
    predlojka_bot.polling(none_stop=True)