from config import predlojka_bot
from analytics.stats import log_event
from database.sqlite_db import get_all_users, get_user_achievements, grant_achievement, get_achievement_by_code


def check_achievements():
    """Проверяет, не заслужил ли кто-то новое достижение, и если да, то выдаёт его и отправляет уведомление"""
    users = get_all_users()
    first_post_achievement = get_achievement_by_code("first_post")
    if first_post_achievement is None:
        return

    # Проверка на достижения по количеству постов
    for user in users:
        user_id = user["user_id"]
        post_count = user["post_counter"]
        user_achievements = get_user_achievements(user_id)
        user_achievements_codes = {a["code"] for a in user_achievements}

        if first_post_achievement["code"] not in user_achievements_codes and post_count >= 1:
            grant_achievement(user_id, first_post_achievement["code"])
            predlojka_bot.send_message(
                user_id,
                f"🎉 Поздравляю вас! Вы получили новое достижение: {first_post_achievement['name']} - {first_post_achievement['description']}"
            )
            log_event(
                "achievement_granted_auto",
                bot="predlojka",
                user_id=user_id,
                metadata={"achievement_code": first_post_achievement["code"]},
            )
