from __future__ import annotations

from .service import WeatherAPIError, format_weather_message, get_weather_forecast


async def send_weather(context):
    """
    Фоновая задача: получить прогноз и отправить его в чат.
    """
    logger = context.logger_factory("weather", persona="Тайлер Дерден")
    bot = context.predlojka_bot
    admin = context.admin_id

    try:
        latitude, longitude = context.config.location
        chat_id = getattr(context.config, "chat_mishas_den", None)

        if chat_id is None:
            logger.say("Не задан chat_mishas_den в config", "error")
            return

        forecast = await get_weather_forecast(
            latitude=latitude,
            longitude=longitude,
            start_hour=12,
            end_hour=20,
        )

        weather_message = format_weather_message(forecast)

        await bot.send_message(chat_id, weather_message)
        logger.say("Прогноз погоды успешно отправлен")

    except WeatherAPIError as e:
        logger.say(f"Не удалось получить прогноз погоды: {e}", "error")

        if admin:
            try:
                await bot.send_message(admin, f"❌ Не удалось получить прогноз погоды.\n{e}")
            except Exception:
                pass

    except Exception as e:
        logger.say(f"Ошибка при отправке погоды: {e}", "error")

        if admin:
            try:
                await bot.send_message(admin, f"❌ Критическая ошибка при отправке погоды: {str(e)[:100]}")
            except Exception:
                pass