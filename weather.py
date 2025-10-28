from data import predlojka_bot, admin, chat_mishas_den, location
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
        list: список словарей с прогнозом по часам или False при ошибке
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
            return False
        
        hourly_data = data['hourly']
        times = hourly_data['time']
        temperatures = hourly_data['temperature_2m']
        weather_codes = hourly_data['weathercode']
        wind_speeds = hourly_data['windspeed_10m']
        
        # Фильтруем данные по нужным часам
        forecast = []
        for i, time_str in enumerate(times):
            time_obj = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            hour = time_obj.hour
            
            if start_hour <= hour <= end_hour:
                forecast.append({
                    'time': time_obj,
                    'hour': hour,
                    'temperature': temperatures[i],
                    'weather_code': weather_codes[i],
                    'wind_speed': wind_speeds[i] * 3.6,  # Переводим в км/ч
                    'icon': WeatherService.get_weather_icon(weather_codes[i])
                })
        
        logger.info(f"Получен прогноз на {len(forecast)} часов")
        return forecast
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка подключения к API погоды: {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе погоды: {e}")
        return False

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
        wind = round(forecast['wind_speed'], 1)
        icon = forecast['icon']
        
        message += f"🕐 {hour:02d}:00 - {icon} {temp}°C | 💨 {wind} км/ч\n"
    
    # Добавляем сводку по дню
    temps = [f['temperature'] for f in forecast_data]
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
            error_msg = "❌ Ошибка при получении прогноза погоды"
            predlojka_bot.send_message(admin, error_msg)
            logger.error("Не удалось получить данные прогноза")
            return
        
        # Форматируем сообщение
        weather_message = format_weather_message(forecast)
        
        # Отправляем в чат
        predlojka_bot.send_message(chat_mishas_den, weather_message)
        logger.info("Прогноз погоды успешно отправлен")
        
    except Exception as e:
        error_msg = f"❌ Критическая ошибка при отправке погоды: {e}"
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
        current = data['current_weather']
        
        return {
            'temperature': current['temperature'],
            'wind_speed': current['windspeed'] * 3.6,
            'weather_code': current['weathercode'],
            'icon': WeatherService.get_weather_icon(current['weathercode'])
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения текущей погоды: {e}")
        return False

if __name__ == "__main__":
    # Тестирование функции
    test_forecast = get_weather_forecast(12, 20)
    if test_forecast:
        print(format_weather_message(test_forecast))
    else:
        print("Ошибка тестирования")