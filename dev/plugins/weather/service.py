from __future__ import annotations

from datetime import datetime
from typing import Optional

import aiohttp

from varibles.dialogue_loader import TEXT

class WeatherAPIError(Exception):
    """Ошибка при получении или разборе погоды."""


class WeatherService:
    """Вспомогательные методы для погоды."""

    WEATHER_CODES = {
        (0,): "☀️",          # Ясно      # чё тебе ясно?
        (1, 2, 3): "🌤️",     # Преимущественно ясно, переменная облачность
        (45, 48): "🌫️",      # Туман
        (51, 53, 55): "🌦️",  # Морось
        (56, 57): "🌧️❄️",    # Ледяная морось
        (61, 63, 65): "🌧️",  # Дождь
        (66, 67): "🌧️❄️",    # Ледяной дождь
        (71, 73, 75): "❄️",  # Снег
        (77,): "🌨️",         # Снежные зерна
        (80, 81, 82): "⛈️",  # Ливни
        (85, 86): "🌨️",      # Снежные ливни
        (95,): "⛈️",         # Гроза
        (96, 99): "⛈️🧊",    # Гроза с градом
    }

    @classmethod
    def get_weather_icon(cls, weather_code: int) -> str:
        """Получить иконку погоды по коду."""
        for codes, icon in cls.WEATHER_CODES.items():
            if weather_code in codes:
                return icon
        return "❓"


async def get_weather_forecast(
    latitude: float,
    longitude: float,
    start_hour: int = 12,
    end_hour: int = 20,
    timeout: int = 10,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """
    Получить прогноз погоды на указанные часы (асинхронно).

    Возвращает список словарей с данными.
    Выбрасывает WeatherAPIError при проблемах с API или форматом ответа.
    """
    today = datetime.now().date()

    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        "hourly=temperature_2m,relativehumidity_2m,weathercode,windspeed_10m&"
        "windspeed_unit=ms&timezone=auto&"
        f"start_date={today}&end_date={today}"
    )

    # Если сессия не передана, создаём временную (закрывается автоматически)
    if session is None:
        async with aiohttp.ClientSession() as temp_session:
            return await _fetch_forecast(temp_session, url, start_hour, end_hour, timeout)
    else:
        return await _fetch_forecast(session, url, start_hour, end_hour, timeout)


async def _fetch_forecast(
    session: aiohttp.ClientSession,
    url: str,
    start_hour: int,
    end_hour: int,
    timeout: int,
) -> list[dict]:
    """Вспомогательная функция для выполнения запроса и парсинга."""
    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()  # выбросит aiohttp.ClientResponseError для 4xx/5xx
            data = await response.json()
    except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as e:
        raise WeatherAPIError(f"Ошибка подключения к API погоды: {e}") from e
    
    except ValueError as e:
        raise WeatherAPIError("API погоды вернул невалидный JSON") from e

    hourly_data = data.get("hourly")
    if not hourly_data:
        raise WeatherAPIError("Некорректный ответ от API погоды")

    times = hourly_data.get("time", [])
    temperatures = hourly_data.get("temperature_2m", [])
    weather_codes = hourly_data.get("weathercode", [])
    wind_speeds = hourly_data.get("windspeed_10m", [])

    if not times:
        raise WeatherAPIError("В ответе API нет почасовых данных")

    forecast: list[dict] = []

    for i, time_str in enumerate(times):
        try:
            if "T" in time_str:
                time_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            else:
                time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M")

            hour = time_obj.hour
            if not (start_hour <= hour <= end_hour):
                continue

            if i >= len(temperatures) or i >= len(weather_codes) or i >= len(wind_speeds):
                continue

            forecast.append(
                {
                    "time": time_obj,
                    "hour": hour,
                    "temperature": temperatures[i],
                    "weather_code": weather_codes[i],
                    "wind_speed": wind_speeds[i],
                    "icon": WeatherService.get_weather_icon(weather_codes[i]),
                }
            )
        except Exception:
            continue

    if not forecast:
        raise WeatherAPIError("Не удалось собрать прогноз на нужные часы")

    return forecast


def format_weather_message(forecast_data: list[dict]) -> str:
    """
    Отформатировать сообщение с прогнозом погоды.
    """
    if not forecast_data:
        return TEXT("err/no_forecast_data")

    current_time = datetime.now().strftime("%H:%M")
    message = TEXT("weather_message", "title", current_time=current_time)

    for forecast in forecast_data:
        hour = "{:02d}".format(forecast["hour"])
        temp = round(forecast["temperature"])
        wind = round(forecast["wind_speed"], 1)
        icon = forecast["icon"]

        message += TEXT("weather_message/hour_info", hour=hour, icon=icon, temp=temp)

    temps = [f["temperature"] for f in forecast_data]
    if temps:
        max_temp = max(temps)
        min_temp = min(temps)
        avg_temp = round(sum(temps) / len(temps), 1)


        # НЕ ДАЙ БОГ!!!! эта херь не будет работать
        message += TEXT("weather_message/period", start=f"{forecast_data[0]['hour']:02d}", final=f"{forecast_data[-1]['hour']:02d}")
        message += TEXT("weather_message/temp_info", max_temp=max_temp, min_temp=min_temp, avg_temp=avg_temp)

    return message


async def get_current_weather(
    latitude: float,
    longitude: float,
    timeout: int = 10,
    session: Optional[aiohttp.ClientSession] = None,
) -> Optional[dict]:
    """
    Получить текущую погоду (асинхронно).
    """
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        "current_weather=true&timezone=auto&windspeed_unit=ms"
    )

    if session is None:
        async with aiohttp.ClientSession() as temp_session:
            return await _fetch_current(temp_session, url, timeout)
    else:
        return await _fetch_current(session, url, timeout)


async def _fetch_current(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int,
) -> Optional[dict]:
    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            data = await response.json()
            current = data.get("current_weather", {})
            if not current:
                return None

            weather_code = current.get("weathercode", 0)
            return {
                "temperature": current.get("temperature", 0),
                "wind_speed": current.get("windspeed", 0),
                "weather_code": weather_code,
                "icon": WeatherService.get_weather_icon(weather_code),
            }
    except Exception:
        return None