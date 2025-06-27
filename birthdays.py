from data import db, predlojka_bot, chat_mishas_den
from tinydb import Query
from datetime import datetime, timedelta

BIRTHDAY_TABLE = "birthdays"





def send_daily_birthdays():
    try:
        text = format_birthdays_list()
        predlojka_bot.send_message(chat_mishas_den, text)
    except Exception as e:
        print(f"Ошибка при отправке дней рождений: {e}")





def add_birthday(user_id, name, date_str):
    """
    Добавляет или обновляет день рождения пользователя.
    date_str — строка в формате 'ДД.ММ' или 'ДД.ММ.ГГГГ'
    """
    try:
        # Преобразуем дату
        if len(date_str.split(".")) == 2:
            bday = datetime.strptime(date_str, "%d.%m")
            year = 2000  # фиктивный год
        else:
            bday = datetime.strptime(date_str, "%d.%m.%Y")
            year = bday.year
        db.table(BIRTHDAY_TABLE).upsert({
            "user_id": user_id,
            "name": name,
            "day": bday.day,
            "month": bday.month,
            "year": year
        }, Query().user_id == user_id)
        return True
    except Exception as e:
        print(f"Ошибка при добавлении дня рождения: {e}")
        return False

def add_birthday_by_username(username, date_str, chat_id):
    try:
        user = predlojka_bot.get_chat_member(chat_id, username)
        first_name = user.user.first_name or ""
        last_name = user.user.last_name or ""
        name = f"{first_name} {last_name}".strip()
        if len(date_str.split(".")) == 2:
            bday = datetime.strptime(date_str, "%d.%m")
            year = 2000
        else:
            bday = datetime.strptime(date_str, "%d.%m.%Y")
            year = bday.year
        db.table(BIRTHDAY_TABLE).upsert({
            "user_id": user.user.id,
            "name": name,
            "username": username,
            "day": bday.day,
            "month": bday.month,
            "year": year
        }, Query().user_id == user.user.id)
        return True, name
    except Exception as e:
        print(f"Ошибка при добавлении дня рождения: {e}")
        return False, None

def get_all_birthdays():
    return db.table(BIRTHDAY_TABLE).all()

def days_until_birthday(day, month):
    today = datetime.now().date()  # только дата, без времени
    this_year = today.year
    try:
        bday = datetime(this_year, month, day).date()
    except ValueError:
        # обработка некорректных дат
        return -1
    if bday < today:
        bday = datetime(this_year + 1, month, day).date()
    return (bday - today).days


def plural_days(n):
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return "дней"
    if n % 10 == 1:
        return "день"
    if 2 <= n % 10 <= 4:
        return "дня"
    return "дней"


def format_birthdays_list():
    bdays = get_all_birthdays()
    if not bdays:
        return "Список дней рождений пуст."
    result = []
    for b in bdays:
        days_left = days_until_birthday(b["day"], b["month"])
        result.append(f'{b["name"]}: {days_left} {plural_days(days_left)}')
    result.sort(key=lambda x: int(x.split(": ")[1].split(" ")[0]))
    return "Ежедневные уведомления о днях рождений подписчиков!\n\n" + "\n".join(result)