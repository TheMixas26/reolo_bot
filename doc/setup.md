# Запуск и настройка

## Требования

- Python `3.12+`
- Telegram bot tokens для нужных ботов
- ключи Yandex Cloud, если используется `#ai`

Установка зависимостей:

```bash
pip install -r requirements.txt
```

## Где должен лежать `config.py`

Проект ожидает файл `dev/config.py`.

Это важно по двум причинам:

- `dev/main.py` импортирует `config` как модуль из каталога `dev`;
- часть путей в коде задана относительно корня репозитория.

Поэтому запускать проект стоит именно так:

```bash
python dev/main.py
```

Запуск из каталога `dev/` может привести к неправильным относительным путям.

## Где менять несекретные параметры

Для публичных настроек проекта теперь есть отдельный файл:

```text
dev/settings.py
```

Туда вынесены:

- названия проекта и ботов;
- username карточного бота;
- отображаемые названия валюты;
- комиссия банковых переводов;
- другие параметры брендинга, которые не должны считаться секретами.

## Пример `dev/config.py`

```python
import telebot
from utils.imperial_сalender import ImperialCalendar

DEBUG_MODE = True

BANK_TOKEN = ""
RPG_TOKEN = ""
PREDLOJKA_TOKEN = ""

if DEBUG_MODE:
    channel = -1009876543210
else:
    channel = -100223456789

admin = 123456789
channel_red = 223456789
chat_mishas_den = -100223456789
backup_chat = 123123123123
location = (55.75, 37.62)

predlojka_bot = telebot.TeleBot(PREDLOJKA_TOKEN)
bank_bot = telebot.TeleBot(BANK_TOKEN)
rpg_bot = telebot.TeleBot(RPG_TOKEN)

calendar = ImperialCalendar("utils/imperial_date_generator.js")

CATALOG_ID = "{yandex_cloud_catalog_id}"
SECRET_KEY = "{yandex_cloud_api_key}"
```

## Что настраивается в `config.py`

- `DEBUG_MODE` — режим запуска для тестового окружения;
- `PREDLOJKA_TOKEN`, `BANK_TOKEN`, `RPG_TOKEN` — токены Telegram-ботов;
- `channel`, `channel_red`, `chat_mishas_den`, `backup_chat` — ID каналов и чатов;
- `admin` — Telegram ID администратора;
- `location` — координаты для прогноза погоды;
- `CATALOG_ID` и `SECRET_KEY` — настройки YandexGPT.

Комиссия переводов теперь задаётся в `dev/settings.py` через `BANK_TRANSFER_COMMISSION`.

## Запуск

Из корня репозитория:

```bash
python dev/main.py
```

При старте:

- поднимается планировщик фоновых задач;
- запускается основной бот предложки;
- запускается RPG-бот;
- банковый бот запускается только если `DEBUG_MODE = False`.

## База данных

Основная база создаётся автоматически по пути:

```text
dev/database/bot.sqlite3
```

Таблицы создаются в `database/sqlite_db.py` при первом запуске.

## Логи

Ошибки и служебный вывод пишутся в:

```text
bot_errors.log
```

Файл пересоздаётся при старте `dev/main.py`.
