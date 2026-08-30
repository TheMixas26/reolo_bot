from core.core_plugin.stats import log_event
from .db import (
    upsert_birthday,
    get_all_birthdays as fetch_all_birthdays,
    update_birthday_name,
    get_birthday, set_personal_notify
)
from datetime import datetime
from random import randint
from varibles.dialogue_loader import TEXT


BIRTHDAY_TABLE = "birthdays"

def _build_personal_congratulation(name: str) -> str:
    return TEXT("personal_bday").format(name=name)


def _build_public_congratulation(name: str) -> str:
    return TEXT("channel_bday").format(name=name)



async def send_daily_birthdays(context):
    """Отправляет ежедневное уведомление в чат с днями рождений."""
    logger = context.logger_factory("birthdays", persona="Никитос")
    try:
        text = await format_birthdays_list(context)
        await context.predlojka_bot.send_message(context.chat_mishas_den, text)
        await context.predlojka_bot.send_message(context.admin_id, TEXT("success/channel_notify"))
        log_event(
            "birthday_daily_sent",
            bot="predlojka",
            chat_id=context.chat_mishas_den,
            metadata={"count": 1},
        )
    except Exception as e:
        logger.say(f"Ошибка при отправке дней рождений: {e}", "error")


async def send_personal_birthday_notifications(context) -> None:
    """
    Отправляет каждому пользователю личное уведомление о его дне рождения.
    """
    logger = context.logger_factory("birthdays", persona="Никитос")
    bdays = await get_all_birthdays()
    sent_count = 0
    for b in bdays:
        if not b.get("personal_notify"):
            continue
        user_id = b.get("user_id")
        name = b.get("name")
        day = b.get("day")
        month = b.get("month")
        days_left = days_until_birthday(day, month)
        subscribers_list = await format_birthdays_list(context, who_asking_flag="personal")

        if days_left == 0:
            first_text = f"🎉 {name}, сегодня ваш день рождения! Поздравляю! 🎂"
        elif days_left > 0:
            first_text = f"Здравствуйте, {name}!\nДо вашего дня рождения осталось {days_left} {plural_days(days_left)}."
        else:
            continue  # в теории, пропуск некоректных дат. В теории.   # И на практике похоже тоже всё хорошо
        try:
            fin_text = f"{first_text}\n\n{subscribers_list}"
            await context.predlojka_bot.send_message(user_id, fin_text)
            sent_count += 1
        except Exception as e:
            logger.say(f"Не удалось отправить личное уведомление для user_id={user_id}: {e}", "error")

    if sent_count:
        log_event(
            "birthday_personal_notifications_sent",
            bot="predlojka",
            metadata={"count": sent_count},
        )



async def add_birthday(context, user_id, name, date_str) -> bool:
    """
    Добавляет или обновляет день рождения пользователя.
    date_str — строка в формате 'ДД.ММ' или 'ДД.ММ.ГГГГ'
    """
    logger = context.logger_factory("birthdays", persona="Никитос")
    try:
        # Преобразуем дату
        if len(date_str.split(".")) == 2:
            bday = datetime.strptime(date_str, "%d.%m")
            year = 2000  # фиктивный год   # почему-то мне смешно с этой строчки))) Может дело в том, что я очень хочу спать)
        else:
            bday = datetime.strptime(date_str, "%d.%m.%Y")
            year = bday.year
        await upsert_birthday(user_id=user_id, name=name, day=bday.day, month=bday.month, year=year)
        return True
    except Exception as e:
        logger.say(f"Ошибка при добавлении дня рождения: {e}", "error")
        return False

async def add_birthday_by_username(context, username, date_str, chat_id) -> tuple[bool, str | None]:
    """Добавляет или обновляет день рождения пользователя по его имени пользователя в Telegram.
    date_str — строка в формате 'ДД.ММ' или 'ДД.ММ.ГГГГ'"""
    logger = context.logger_factory("birthdays", persona="Никитос")
    try:
        user = await context.predlojka_bot.get_chat_member(chat_id, username)
        first_name = user.user.first_name or ""
        last_name = user.user.last_name or ""
        name = f"{first_name} {last_name}".strip()
        if len(date_str.split(".")) == 2:
            bday = datetime.strptime(date_str, "%d.%m")
            year = 2000
        else:
            bday = datetime.strptime(date_str, "%d.%m.%Y")
            year = bday.year
        await upsert_birthday(
            user_id=user.user.id,
            name=name,
            username=username,
            day=bday.day,
            month=bday.month,
            year=year,
        )
        return True, name
    except Exception as e:
        logger.say(f"Ошибка при добавлении дня рождения: {e}", "error")
        return False, None

async def get_all_birthdays() -> list[dict]:
    """Получает список всех дней рождений из базы данных."""
    return await fetch_all_birthdays()

def days_until_birthday(day, month) -> int:
    """Вычисляет количество дней до следующего дня рождения."""
    today = datetime.now().date()  # только дата, без времени    # мне кто-нибудь скажет, зачем я это комментировал?...
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


async def refresh_user_names(context, chat_id: int) -> None:
    """Обновляет имена всех пользователей в базе, если они изменились."""
    logger = context.logger_factory("birthdays", persona="Никитос")
    users = await get_all_birthdays()
    for user in users:
        user_id = user.get("user_id")
        try:
            chat_member = await context.predlojka_bot.get_chat_member(chat_id, user_id)
            first_name = chat_member.user.first_name or ""
            last_name = chat_member.user.last_name or ""
            name = f"{first_name} {last_name}".strip()
            if user.get("name") != name:
                await update_birthday_name(user_id, name)
        except Exception as e:
            logger.say(f"Не удалось обновить имя для user_id={user_id}: {e}", "error")



async def format_birthdays_list(context, who_asking_flag='channel') -> str:
    """Формирует текст с ближайшими днями рождений.
    who_asking_flag: 'channel' — для ежедневного уведомления, 'personal' — для личного сообщения пользователю."""
    await refresh_user_names(context, context.chat_mishas_den)
    bdays = await get_all_birthdays()
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
    if who_asking_flag == 'channel' or who_asking_flag == 0:
        return "Ежедневные уведомления о днях рождений подписчиков!\n\n" + "\n".join(lines)
    elif who_asking_flag == 'personal' or who_asking_flag == 1:
        lines = lines[:3]
        return "Вот ближайшие дни рождения других пользователей!\n" + "\n".join(lines)



async def send_birthday_congratulation(context) -> None:
    """Отправляет поздравление с днем рождения пользователю."""
    logger = context.logger_factory("birthdays", persona="Никитос")
    bdays = await get_all_birthdays()
    dm_sent = 0
    channel_sent = 0
    for b in bdays:
        user_id = b.get("user_id")
        name = b.get("name")
        day = b.get("day")
        month = b.get("month")
        days_left = days_until_birthday(day, month)
        if days_left == 0:
            congratulation_text_dm = _build_personal_congratulation(name)
            congratulation_text_ch = _build_public_congratulation(name)

            try:
                await context.predlojka_bot.send_message(user_id, congratulation_text_dm)
                dm_sent += 1
            except Exception as e:
                logger.say(f"Ошибка личного поздравления для {user_id}: {e}", "error")

            try:
                await context.predlojka_bot.send_message(context.channel, congratulation_text_ch)
                channel_sent += 1
            except Exception as e:
                logger.say(f"Ошибка публичного поздравления для {user_id}: {e}", "error")

    if dm_sent:
        log_event(
            "birthday_personal_congratulations_sent",
            bot="predlojka",
            metadata={"count": dm_sent},
        )
    if channel_sent:
        log_event(
            "birthday_channel_congratulations_sent",
            bot="predlojka",
            chat_id=context.channel,
            metadata={"count": channel_sent},
        )



async def get_user_birthday(user_id):
    return await get_birthday(user_id)


async def change_personal_notify(user_id, flag):
    await set_personal_notify(user_id, flag)
