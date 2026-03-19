from config import predlojka_bot, chat_mishas_den, admin, channel
from database.sqlite_db import (
    upsert_birthday,
    get_all_birthdays as fetch_all_birthdays,
    update_birthday_name,
)
from datetime import datetime, timedelta
from random import randint

BIRTHDAY_TABLE = "birthdays"





def send_daily_birthdays():
    """Отправляет ежедневное уведомление в чат с днями рождений."""
    try:
        text = format_birthdays_list()
        predlojka_bot.send_message(chat_mishas_den, text)
        predlojka_bot.send_message(admin, "Уведомление направлено!")
    except Exception as e:
        print(f"Ошибка при отправке дней рождений: {e}")





def add_birthday(user_id, name, date_str) -> bool:
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
        upsert_birthday(user_id=user_id, name=name, day=bday.day, month=bday.month, year=year)
        return True
    except Exception as e:
        print(f"Ошибка при добавлении дня рождения: {e}")
        return False

def add_birthday_by_username(username, date_str, chat_id) -> tuple[bool, str | None]:
    """Добавляет или обновляет день рождения пользователя по его имени пользователя в Telegram.
    date_str — строка в формате 'ДД.ММ' или 'ДД.ММ.ГГГГ'"""
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
        upsert_birthday(
            user_id=user.user.id,
            name=name,
            username=username,
            day=bday.day,
            month=bday.month,
            year=year,
        )
        return True, name
    except Exception as e:
        print(f"Ошибка при добавлении дня рождения: {e}")
        return False, None

def get_all_birthdays() -> list[dict]:
    """Получает список всех дней рождений из базы данных."""
    return fetch_all_birthdays()

def days_until_birthday(day, month) -> int:
    """Вычисляет количество дней до следующего дня рождения."""
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


def plural_days(n: int) -> str:
    """Возвращает правильное склонение слова "день" в зависимости от количества."""
    n = abs(n)
    if 11 <= n % 100 <= 14:
        return "дней"
    if n % 10 == 1:
        return "день"
    if 2 <= n % 10 <= 4:
        return "дня"
    return "дней"


def refresh_user_names(chat_id: int) -> None:
    """
    Обновляет имена всех пользователей в базе, если они изменились.
    """
    users = get_all_birthdays()
    for user in users:
        user_id = user.get("user_id")
        try:
            chat_member = predlojka_bot.get_chat_member(chat_id, user_id)
            first_name = chat_member.user.first_name or ""
            last_name = chat_member.user.last_name or ""
            name = f"{first_name} {last_name}".strip()
            if user.get("name") != name:
                update_birthday_name(user_id, name)
        except Exception as e:
            print(f"Не удалось обновить имя для user_id={user_id}: {e}")



def format_birthdays_list(who_asking_flag=0) -> str:
    """Формирует текст с ближайшими днями рождений.
    who_asking_flag: 0 — для ежедневного уведомления, 1 — для личного сообщения пользователю."""
    refresh_user_names(chat_mishas_den)
    bdays = get_all_birthdays()
    if not bdays:
        return "Список дней рождений пуст."
    result = []

    for b in bdays:
        days_left = days_until_birthday(b["day"], b["month"])
        if days_left == 0:
            result.append((0, f'> {b["name"]}: сегодня день рождения! 🎉'))
        else:
            result.append((days_left, f'> {b["name"]}: {days_left} {plural_days(days_left)}'))

    if randint(1, 100) == 1:
        result.append((999999, f'> Предложка Империи: 999 999 дней до выхода из подвала...'))

    result.sort(key=lambda x: x[0])
    lines = [x[1] for x in result]
    if who_asking_flag == 0:
        return "Ежедневные уведомления о днях рождений подписчиков!\n\n" + "\n".join(lines)
    elif who_asking_flag == 1:
        lines = lines[:3]
        return "Вот ближайшие дни рождения других пользователей!\n" + "\n".join(lines)

def send_personal_birthday_notifications() -> None:
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


def send_birthday_congratulation() -> None:
    """Отправляет поздравление с днем рождения пользователю."""
    bdays = get_all_birthdays()
    for b in bdays:
        user_id = b.get("user_id")
        name = b.get("name")
        day = b.get("day")
        month = b.get("month")
        days_left = days_until_birthday(day, month)
        if days_left == 0:
            
            # TODO: см строчку ниже
            # ! Бляха, я не могу сейчас решить вопрос, нет времени, но поздравление должно генерироваться через нейросеть не забыть бы...
            congratulation_text_dm = f"Здравствуйте, {name}! Кажется, у вас сегодня день рождения... Если конечно мои подвальные записи не врут)\n\nМы всей Империей вас поздравляем! +1000 соуиального рейтинга и бесчисленное вам уважение!\n\nСпасибо вам за все ваши посты в Предложке (если вы конечно отправляли), мне бесконечно приятно, что наш канал живёт благодаря таким пользователям, как вы! С праздником вас, {name}!"

            congratulation_text_ch = f"Товарищи подписчики! Сегодня не обычный день...\n\n🎉 Сегодня день рождения у нашего дорогого подписчика {name}! Давайте поздравим его в комментариях и пожелаем всего самого лучшего! 🎂\n\n{name}, мы поздравляем вас с днем рождения! Счастья вам, здоровья и успехов! Мы вас обожаем!!!"

            try:
                predlojka_bot.send_message(user_id, congratulation_text_dm)
            except Exception as e:
                print(f"Ошибка личного поздравления для {user_id}: {e}")

            try:
                predlojka_bot.send_message(channel, congratulation_text_ch)
            except Exception as e:
                print(f"Ошибка публичного поздравления для {user_id}: {e}")