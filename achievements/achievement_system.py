from config import predlojka_bot
from database.sqlite_db import get_all_users, get_user_achievements, grant_achievement, get_all_achievements, get_achievements_by_code


def check_achievements():
    """Проверяет, не заслужил ли кто-то новое достижение, и если да, то выдаёт его и отправляет уведомление"""

    
    users = get_all_users()
    

    # Проверка на достижения по количеству постов
    for user in users:
        user_id = user['user_id']
        post_count = user['post_counter']
        user_achievements = get_user_achievements(user_id)
        
        user_achievements_codes = {a["code"] for a in user_achievements}

        for achievement in get_achievements_by_code('first_post'):
            if achievement["code"] not in user_achievements_codes and post_count >= 1:
                grant_achievement(user_id, achievement["code"])
                # Отправляем уведомление пользователю о новом достижении
                predlojka_bot.send_message(
                    user_id,
                    f"🎉 Поздравляем! Вы получили новое достижение: {achievement['name']} - {achievement['description']}"
                )