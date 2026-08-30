from core.core_plugin.stats import log_event
from database.sqlite_db import get_all_users
from .db import get_user_achievements, grant_achievement, get_achievement_by_code

from varibles.dialogue_loader import TEXT

async def check_achievements(context):
    """Проверяет, не заслужил ли кто-то новое достижение, и если да, то выдаёт его и отправляет уведомление"""
    users = await get_all_users()
    first_post_achievement = await get_achievement_by_code("first_post")
    if first_post_achievement is None:
        return

    # Проверка на достижения по количеству постов

    # TODO: мы же не собирамся добавлять сюда КАЖДОЕ условие достижения?... Стоит разработать какую-то автоматическую систему....

    for user in users:
        user_id = user["user_id"]
        post_count = user["post_counter"]
        user_achievements = await get_user_achievements(user_id)
        user_achievements_codes = {a["code"] for a in user_achievements}

        if first_post_achievement["code"] not in user_achievements_codes and post_count >= 1:
            await grant_achievement(user_id, first_post_achievement["code"])
            await context.predlojka_bot.send_message(
                user_id,
                TEXT("new_achievment", name=first_post_achievement['name'], desc=first_post_achievement['description'])
            )
            log_event(
                "achievement_granted_auto",
                bot="predlojka",
                user_id=user_id,
                metadata={"achievement_code": first_post_achievement["code"]},
            )
