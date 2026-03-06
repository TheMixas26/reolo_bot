from config import predlojka_bot, admin, chat_mishas_den, location
import requests
from datetime import datetime, timedelta
import logging

# Настройка логирования для отслеживания ошибок
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherService:
    """Класс для работы с API погоды"""
    
    # Коды погоды и соответствующие им иконки
    WEATHER_CODES = {
        (0,): "☀️",   # Ясно
        (1, 2, 3): "🌤️",  # Преимущественно ясно, переменная облачность
        (45, 48): "🌫️",  # Туман
        (51, 53, 55): "🌦️",  # Морось
        (56, 57): "🌧️❄️",  # Ледяная морось
        (61, 63, 65): "🌧️",  # Дождь
        (66, 67): "🌧️❄️",  # Ледяной дождь
        (71, 73, 75): "❄️",  # Снег
        (77): "🌨️",  # Снежные зерна
        (80, 81, 82): "⛈️",  # Ливни
        (85, 86): "🌨️",  # Снежные ливни
        (95,): "⛈️",  # Гроза
        (96, 99): "⛈️🧊",  # Гроза с градом
    }
    
    @staticmethod
    def get_weather_icon(weather_code):
        """Получить иконку погоды по коду"""
        for codes, icon in WeatherService.WEATHER_CODES.items():
            if weather_code in codes:
                return icon
        return "❓"  # Если код неизвестен

def get_weather_forecast(start_hour=12, end_hour=20):
    """
    Получить прогноз погоды на указанные часы
    
    Args:
        start_hour (int): начальный час (по умолчанию 12)
        end_hour (int): конечный час (по умолчанию 20)
    
    Returns:
        list: список словарей с прогнозом по часам или None при ошибке
    """
    try:
        # Получаем текущую дату
        today = datetime.now().date()
        
        # Формируем URL для запроса почасового прогноза
        url = (f'https://api.open-meteo.com/v1/forecast?'
               f'latitude={location[0]}&longitude={location[1]}&'
               f'hourly=temperature_2m,relativehumidity_2m,weathercode,windspeed_10m&'
               f'windspeed_unit=ms&timezone=auto&'
               f'start_date={today}&end_date={today}')
        
        logger.info(f"Запрос погоды: {url}")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Вызовет исключение для плохих статусов
        
        data = response.json()
        
        if 'hourly' not in data:
            logger.error("Некорректный ответ от API погоды")
            return None
        
        hourly_data = data['hourly']
        times = hourly_data.get('time', [])
        temperatures = hourly_data.get('temperature_2m', [])
        weather_codes = hourly_data.get('weathercode', [])
        wind_speeds = hourly_data.get('windspeed_10m', [])
        
        if not times:
            logger.error("Нет данных о времени в ответе API")
            return None
        
        # Фильтруем данные по нужным часам
        forecast = []
        for i, time_str in enumerate(times):
            try:
                # Пробуем разные форматы времени
                if 'T' in time_str:
                    time_obj = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                else:
                    time_obj = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                
                hour = time_obj.hour
                
                if start_hour <= hour <= end_hour:
                    # Проверяем, что у нас есть данные для всех полей
                    if i < len(temperatures) and i < len(weather_codes) and i < len(wind_speeds):
                        forecast.append({
                            'time': time_obj,
                            'hour': hour,
                            'temperature': temperatures[i],
                            'weather_code': weather_codes[i],
                            'wind_speed': wind_speeds[i],  # Оставляем в м/с для API open-meteo
                            'icon': WeatherService.get_weather_icon(weather_codes[i])
                        })
            except Exception as e:
                logger.warning(f"Ошибка обработки времени {time_str}: {e}")
                continue
        
        logger.info(f"Получен прогноз на {len(forecast)} часов")
        return forecast if forecast else None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка подключения к API погоды: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе погоды: {e}")
        return None

def format_weather_message(forecast_data):
    """
    Форматировать сообщение с прогнозом погоды
    
    Args:
        forecast_data (list): данные прогноза
    
    Returns:
        str: отформатированное сообщение
    """
    if not forecast_data:
        return "❌ Не удалось получить данные о погоде"
    
    current_time = datetime.now().strftime("%H:%M")
    
    message = f"🌤️ Прогноз погоды на сегодня (обновлено {current_time}):\n\n"
    
    for forecast in forecast_data:
        hour = forecast['hour']
        temp = round(forecast['temperature'])
        wind = round(forecast['wind_speed'], 1)  # В м/с
        icon = forecast['icon']
        
        message += f"🕐 {hour:02d}:00 - {icon} {temp}°C | 💨 {wind} м/с\n"
    
    # Добавляем сводку по дню
    temps = [f['temperature'] for f in forecast_data]
    if temps:
        max_temp = max(temps)
        min_temp = min(temps)
        avg_temp = round(sum(temps) / len(temps), 1)
        
        message += f"\n📊 Сводка за период {forecast_data[0]['hour']:02d}:00-{forecast_data[-1]['hour']:02d}:00:\n"
        message += f"• Макс: {max_temp}°C | Мин: {min_temp}°C | Средн: {avg_temp}°C"
    
    return message

def send_weather():
    """
    Отправить прогноз погоды в чат
    """
    try:
        # Получаем прогноз с 12:00 до 20:00
        forecast = get_weather_forecast(start_hour=12, end_hour=20)
        
        if not forecast:
            error_msg = "❌ Ошибка при получении прогноза погоды. Проверьте подключение к интернету и корректность координат."
            if admin:
                predlojka_bot.send_message(admin, error_msg)
            logger.error("Не удалось получить данные прогноза")
            return
        
        # Форматируем сообщение
        weather_message = format_weather_message(forecast)
        
        # Отправляем в чат
        predlojka_bot.send_message(chat_mishas_den, weather_message)
        logger.info("Прогноз погоды успешно отправлен")
        
    except Exception as e:
        error_msg = f"❌ Критическая ошибка при отправке погоды: {str(e)[:100]}"
        if admin:
            predlojka_bot.send_message(admin, error_msg)
        logger.error(f"Ошибка при отправке погоды: {e}")

# Дополнительная функция для получения текущей погоды (если нужна)
def get_current_weather():
    """
    Получить текущую погоду (альтернативная функция)
    """
    try:
        url = (f'https://api.open-meteo.com/v1/forecast?'
               f'latitude={location[0]}&longitude={location[1]}&'
               f'current_weather=true&timezone=auto&windspeed_unit=ms')
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        current = data.get('current_weather', {})
        
        if not current:
            return None
        
        return {
            'temperature': current.get('temperature', 0),
            'wind_speed': current.get('windspeed', 0),
            'weather_code': current.get('weathercode', 0),
            'icon': WeatherService.get_weather_icon(current.get('weathercode', 0))
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения текущей погоды: {e}")
        return None

if __name__ == "__main__":
    # Тестирование функции
    print("Тестирование прогноза погоды...")
    print(f"Используемые координаты: {location}")
    
    test_forecast = get_weather_forecast(12, 20)
    if test_forecast:
        print("Прогноз получен успешно:")
        print(format_weather_message(test_forecast))
        
        # Тестируем текущую погоду
        print("\nТестирование текущей погоды...")
        current = get_current_weather()
        if current:
            print(f"Текущая погода: {current['temperature']}°C, ветер {current['wind_speed']} м/с {current['icon']}")
    else:
        print("Ошибка: не удалось получить прогноз")
        
        # Проверяем текущую погоду как fallback
        print("\nПробуем получить текущую погоду...")
        current = get_current_weather()
        if current:
            print(f"Текущая погода: {current['temperature']}°C, ветер {current['wind_speed']} м/с {current['icon']}")