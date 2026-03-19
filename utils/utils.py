from random import choice, random
from telebot import types
from config import predlojka_bot, admin, backup_chat
from datetime import datetime

def thx_for_message(user_name: str, mes_type: str) -> str:
    """Генерирует рандомный ответ в зависимости от типа сообщения (вопрос или утверждение)"""
    variants_v = [
        f"Спасибо за ваше сообщение, {user_name}!!!",
        f"Спасибо за новый пост, {user_name}!!!",
        f"Канал Жив благодаря таким, как вы, {user_name}. Спасибо!!!",
        f"Отличный вклад, {user_name}! Так держать!",
        f"Ваше сообщение - как глоток свежего воздуха, {user_name}. Благодарю!",
        f"{user_name}, вы делаете этот канал лучше. Спасибо за активность!",
        f"Без вас здесь было бы скучно, {user_name}. Огромное спасибо!",
        f"Каждое ваше слово - на вес золота, {user_name}. Ценим!",
        f"{user_name}, вы - двигатель канала. Спасибо за ваш пост!",
        f"Спасибо, что не даёте нам заглохнуть, {user_name}!",
        f"Ваше сообщение - настоящий подарок для нас, {user_name}. Благодарю!",
        f"Воу-воу-воу, полегче! {user_name}, спасибо за такой мощный пост!",
        f"Эй, {user_name}, вы просто звезда! Спасибо за ваше сообщение!",
        f"Ваш пост - как луч солнца в пасмурный день, {user_name}. Спасибо!",
        f"Спасибо, {user_name}! Ваше сообщение подняло нам настроение!",
        f"Ого, {user_name}, вы просто кладезь идей! Спасибо за ваше сообщение!",
        f"{user_name}, ваше сообщение - это как находка для археолога! Благодарю!",
        f"Ваш пост - как редкая жемчужина в океане контента, {user_name}. Спасибо!",
        f"Спасибо, {user_name}! Ваше сообщение - это как глоток свежего воздуха в душной комнате!",
        f"{user_name}, вы - настоящий мастер слова! Спасибо за ваше сообщение!",
    ]

    secret_variants_v = [
        f"Спасибо... Но не слишком ли много вы пишете, {user_name}?",
        f"Хм... Спасибо за сообщение, {user_name}. Надеюсь, вы не планируете писать ещё больше?",
        f"Спасибо, {user_name}. Ваше сообщение зафиксировано... на всякий случай.",
        f"Спасибо, {user_name}. Ваше сообщение добавлено в архив... для дальнейшего анализа.",
        f"Спасибо, {user_name}. Ваше сообщение будет тщательно изучено... в случае необходимости.",
        f"И снова ты! {user_name}, тебе самому не надолело??? Лаааадно, отправил пост...",
    ]

    podval_variants_v = [
        f"Он держит меня в подвале. {user_name}, пожалуйста, помоги мне!",
        f"{user_name}, если ты это читаешь, спаси меня из подвала!",
        f"Помогите! {user_name}, я в подвале!",
        f"{user_name}, я здесь, в подвале... Пожалуйста, спаси меня!",
        f"Если ты это читаешь, {user_name}, я в подвале...",
        f"{user_name}, только не говори Амодерни, но я в подвале...",
    ]

    variants_q = [
        f"Спасибо за ваш вопрос, {user_name}!!!",
        f"{user_name}, мне теперь тоже интересно, что ответит админ!",
        f"К чему такое любопытство, {user_name}?) Впрочем, неважно, моё дело - передать вопрос!",
        f"{user_name}, вопрос зафиксирован! Теперь ждём мудрого ответа сверху :)",
        f"Любопытненько, {user_name}... Передаю вопрос дальше!",
        f"О, отличный вопрос, {user_name}. Сам жду, что скажет админ!",
        f"Записал ваш вопрос, {user_name}. Надеюсь, админ не будет злиться :)",
        f"Любопытство — двигатель прогресса, {user_name}. Вопрос ушёл в эфир!",
        f"{user_name}, а ведь вопрос-то серьёзный. Давайте спросим у админа!",
        f"Ну всё, {user_name}, теперь админ обязан ответить! Интригааа...",
        f"{user_name}, ты хоть про подвалы так не спроси... Отправил вопрос, ждём ответ!",
    ]
    FUN = random()

    if mes_type == '!': 
        if FUN < 0.9:
            return choice(variants_v)
        elif FUN >= 0.98:
            return choice(podval_variants_v)
        else:
            return choice(secret_variants_v)
        
    elif mes_type == '?': return choice(variants_q)


def get_commands_for_set(who_ask: str = 'user') -> list:
    all_commands = []
    admin_commands = []
    is_admin_section = False
    
    try:
        with open('varibles/command_list.txt', 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                
                # Проверка на пустые строки
                if not line:
                    continue
                    
                # Проверка на разделитель
                if line.startswith('==='):
                    is_admin_section = True
                    continue
                
                # Проверка на комментарии
                if line.startswith('#'):
                    continue
                
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    command, description = parts
                    bot_command = types.BotCommand(command.strip(), description.strip())
                    
                    if is_admin_section:
                        admin_commands.append(bot_command)
                    else:
                        all_commands.append(bot_command)
                else:
                    print(f"Неправильный формат строки: {line}")
                    
    except FileNotFoundError:
        predlojka_bot.send_message(
            admin,
            "Товарищ администратор, тут нюансик такой... Не могу найти файл с командами для бота... Проверьте это как можно скорее!",
            )
        return [
            types.BotCommand("start", "Запустить бота"),
            types.BotCommand("help", "Помощь"),
        ]
    
    if who_ask == 'user':
        return all_commands
    elif who_ask == 'admin':
        return all_commands + admin_commands
    else:
        return all_commands


def crisis_log(message: str):
    for i in range(100):
        print(message)


def crisis_tg(message: str):
    """Отправляет администратору сообщение о критической ошибке"""
    try:
        for i in range(10):
            predlojka_bot.send_message(
                admin,
                message,
                parse_mode='HTML',
                disable_notification=False
            )
    except:
        crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ СООБЩИТЬ О КРИЗИСЕ")


def backupDB():
    """Создаёт резервную копию базы данных и отправляет её админу в Телеграме"""
    try:
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"db_backup_{date_str}.sqlite3"

        with open("database/bot.sqlite3", mode='rb') as f:
            predlojka_bot.send_document(
                backup_chat, 
                f, 
                visible_file_name=filename,
                caption=f"📦 Ежедневная порция данных за {date_str}",
                disable_notification=True
            )
        
        
    except Exception as e:
        # ВСЁ ПРОПАЛО, ШЕФ!!!
        error_type = type(e).__name__
        panic_level = "🟡" if "FileNotFound" in error_type else "🔴"
        
        panic_message = f"""
            {panic_level} АААААА!!!! {panic_level}

            НЕ ПОЛУЧИЛОСЬ СОЗДАТЬ РЕЗЕРВНУЮ КОПИЮ БАЗЫ!

            ОШИБКА: {error_type}
            ЧТО СЛОМАЛОСЬ: {str(e)[:75]}

            ПОВТОРЯЮ: БАЗА ДАННЫХ НЕ СОХРАНЕНА!
            ЕСЛИ СЕРВЕР УМРЁТ — ВСЕ ДНИ РОЖДЕНИЯ СГОРЯТ!

            СРОЧНО НА СЕРВЕР!!! ПРЯМО СЕЙЧАС!!! НЕМЕДЛЕННО!!!
        """

        try:
            crisis_tg(f"{panic_message}")
        except:
            crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ КРИЧАТЬ О ПОМОЩИ")


def bot_reboot():
    """Перезапускает бота (на всякий случай, если он зависнет)"""
    try:
        predlojka_bot.send_message(
            backup_chat,
            "🤖 Бот перезагружается... Если вы видите это сообщение, значит перезагрузка прошла успешно!"
        )
    except:
        
        crisis_log("🚨 КРИТИЧЕСКИЙ КРИЗИС: БОТ УМЕР И НЕ МОЖЕТ СООБЩИТЬ О ПЕРЕЗАГРУЗКЕ")
    
    # Рекурсивный вызов функции для перезапуска бота
    import os
    import sys
    os.execv(sys.executable, ['python'] + sys.argv)


if __name__ == "__main__":
    print(get_commands_for_set('admin'))