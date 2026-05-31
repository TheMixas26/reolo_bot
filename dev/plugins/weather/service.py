from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests


class WeatherAPIError(Exception):
    """Ошибка при получении или разборе погоды."""


class WeatherService:
    """Вспомогательные методы для погоды."""

    WEATHER_CODES = {
        (0,): "☀️",        # Ясно
        (1, 2, 3): "🌤️",  # Преимущественно ясно, переменная облачность
        (45, 48): "🌫️",   # Туман
        (51, 53, 55): "🌦️",  # Морось
        (56, 57): "🌧️❄️",  # Ледяная морось
        (61, 63, 65): "🌧️",  # Дождь
        (66, 67): "🌧️❄️",  # Ледяной дождь
        (71, 73, 75): "❄️",  # Снег
        (77,): "🌨️",      # Снежные зерна
        (80, 81, 82): "⛈️",  # Ливни
        (85, 86): "🌨️",   # Снежные ливни
        (95,): "⛈️",      # Гроза
        (96, 99): "⛈️🧊",  # Гроза с градом
    }

    @classmethod
    def get_weather_icon(cls, weather_code: int) -> str:
        """Получить иконку погоды по коду."""
        for codes, icon in cls.WEATHER_CODES.items():
            if weather_code in codes:
                return icon
        return "❓"


def get_weather_forecast(
    latitude: float,
    longitude: float,
    start_hour: int = 12,
    end_hour: int = 20,
    timeout: int = 10,
) -> list[dict]:
    """
    Получить прогноз погоды на указанные часы.

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

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise WeatherAPIError(f"Ошибка подключения к API погоды: {e}") from e

    try:
        data = response.json()
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
        return "❌ Не удалось получить данные о погоде"

    current_time = datetime.now().strftime("%H:%M")
    message = f"🌤️ Прогноз погоды на сегодня (обновлено {current_time}):\n\n"

    for forecast in forecast_data:
        hour = forecast["hour"]
        temp = round(forecast["temperature"])
        wind = round(forecast["wind_speed"], 1)
        icon = forecast["icon"]

        message += f"🕐 {hour:02d}:00 - {icon} {temp}°C | 💨 {wind} м/с\n"

    temps = [f["temperature"] for f in forecast_data]
    if temps:
        max_temp = max(temps)
        min_temp = min(temps)
        avg_temp = round(sum(temps) / len(temps), 1)

        message += f"\n📊 Сводка за период {forecast_data[0]['hour']:02d}:00-{forecast_data[-1]['hour']:02d}:00:\n"
        message += f"• Макс: {max_temp}°C | Мин: {min_temp}°C | Средн: {avg_temp}°C"

    return message


def get_current_weather(
    latitude: float,
    longitude: float,
    timeout: int = 10,
) -> Optional[dict]:
    """
    Получить текущую погоду.
    """
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        "current_weather=true&timezone=auto&windspeed_unit=ms"
    )

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
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