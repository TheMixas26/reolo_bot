from data import db, predlojka_bot, chat_mishas_den, admin
from tinydb import Query
from datetime import datetime, timedelta

BIRTHDAY_TABLE = "birthdays"





def send_daily_birthdays():
    try:
        text = format_birthdays_list()
        predlojka_bot.send_message(chat_mishas_den, text)
        predlojka_bot.send_message(admin, "Уведомление направлено!")
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


def refresh_user_names(chat_id):
    """
    Обновляет имена всех пользователей в базе, если они изменились.
    """
    table = db.table(BIRTHDAY_TABLE)
    users = table.all()
    for user in users:
        user_id = user.get("user_id")
        try:
            chat_member = predlojka_bot.get_chat_member(chat_id, user_id)
            first_name = chat_member.user.first_name or ""
            last_name = chat_member.user.last_name or ""
            name = f"{first_name} {last_name}".strip()
            if user.get("name") != name:
                table.update({"name": name}, Query().user_id == user_id)
        except Exception as e:
            print(f"Не удалось обновить имя для user_id={user_id}: {e}")



def format_birthdays_list(who_asking_flag=0):
    refresh_user_names(chat_mishas_den)
    bdays = get_all_birthdays()
    if not bdays:
        return "Список дней рождений пуст."
    result = []
    
    for b in bdays:
        days_left = days_until_birthday(b["day"], b["month"])
        if days_left == 0:
            result.append(f'> {b["name"]}: сегодня день рождения! 🎉')
        else:
            result.append(f'> {b["name"]}: {days_left} {plural_days(days_left)}')

    result.sort(key=lambda x: int(x.split(": ")[1].split(" ")[0]))
    if who_asking_flag == 0: return "Ежедневные уведомления о днях рождений подписчиков!\n\n" + "\n".join(result)
    elif who_asking_flag == 1: 
        result = result[:2]
        return "Вот ближайшие дни рождения других пользователей!\n" + "\n".join(result)

def send_personal_birthday_notifications():
    """
    Отправляет каждому пользователю личное уведомление о его дне рождения.
    """
    bdays = get_all_birthdays()
    for b in bdays:
        if not b.get("personal_notify"):
            continue
        user_id = b.get("user_id")
        name = b.get("name")
        day = b.get("day")
        month = b.get("month")
        days_left = days_until_birthday(day, month)
        subscribers_list = format_birthdays_list(who_asking_flag=1)

        if days_left == 0:
            first_text = f"🎉 {name}, сегодня ваш день рождения! Поздравляю! 🎂"
        elif days_left > 0:
            first_text = f"Здравствуйте, {name}!\nДо вашего дня рождения осталось {days_left} {plural_days(days_left)}."
        else:
            continue  # в теории, пропуск некоректных дат. В теории.
        try:
            fin_text = f"{first_text}\n\n{subscribers_list}"
            predlojka_bot.send_message(user_id, fin_text)
        except Exception as e:
            print(f"Не удалось отправить личное уведомление для user_id={user_id}: {e}")