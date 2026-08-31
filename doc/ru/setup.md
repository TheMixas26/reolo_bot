# Запуск и настройка


> [INFO]
> Проект полностью сменил архитектуру с синхронной на ассинхронную.
> Это значит, что любая информация здесь модет быть недостоверной.
> Устаревшая информация отмечается [!] перед началом блока. Будьте бдительны!


## Требования

- Python `3.14+`
- Telegram bot tokens для нужных ботов
- ключи Yandex Cloud, если используется `#ai`
- VK token, если нужна публикация во VK

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

Для публичных настроек проекта есть отдельный файл:

```text
dev/settings.py
```

Туда вынесены:

- названия проекта и ботов;
- username карточного бота;
- отображаемые названия валюты;
- комиссия банковых переводов;
- названия календаря;
- другие параметры брендинга, которые не должны считаться секретами.

## Пример `dev/config.py`

```python
DEBUG_MODE = True
HIBERNATION = False

BANK_TOKEN = ""
RPG_TOKEN = ""
PREDLOJKA_TOKEN = ""

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "database")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)
POSTGRES_DSN = DATABASE_URL

if DEBUG_MODE:
    channel = -1009876543210
else:
    channel = -100223456789

admin = 123456789
channel_red = 223456789
chat_mishas_den = -100223456789
backup_chat = 123123123123
location = (55.75, 37.62)

CATALOG_ID = "{yandex_cloud_catalog_id}"
SECRET_KEY = "{yandex_cloud_api_key}"

# Опционально: публикация во VK
VK_TOKEN = ""
VK_OWNER_ID = None
VK_GROUP_ID = None
VK_API_VERSION = "5.199"
```

## Что настраивается в `config.py`

- `DEBUG_MODE` — режим запуска для тестового окружения;
- `HIBERNATION` — ограниченный режим работы предложки;
- `PREDLOJKA_TOKEN`, `BANK_TOKEN`, `RPG_TOKEN` — токены Telegram-ботов;
- `channel`, `channel_red`, `chat_mishas_den`, `backup_chat` — ID каналов и чатов;
- `admin` — Telegram ID администратора;
- `location` — координаты для прогноза погоды;
- `CATALOG_ID` и `SECRET_KEY` — настройки YandexGPT;
- `VK_TOKEN`, `VK_OWNER_ID`, `VK_GROUP_ID`, `VK_API_VERSION` — опциональные настройки VK.

Комиссия переводов задаётся в `dev/settings.py` через `BANK_TRANSFER_COMMISSION`.

Имперский календарь создаётся внутри `dev/plugins/calendar/service.py` и читает JavaScript-правила из `dev/utils/imperial_date_generator.js`.

## Запуск

Из корня репозитория:

```bash
python dev/main.py
```

При старте:

- пересоздаётся `bot_errors.log`;
- загружаются тексты плагинов;
- регистрируются обработчики и фоновые задачи;
- запускаются тесты командой `python -m pytest tests/ -v` ([!]);
- если тесты прошли, стартует планировщик;
- запускаются основной бот, RPG-бот и банковый бот ([!]);
- запускается VK-listener, если VK-адаптер настроен.

Если тесты падают, `dev/main.py` завершает работу и боты не запускаются.

## [!] База данных

[!] Основная база создаётся автоматически по пути:

```text [!]
dev/database/bot.sqlite3
```

[!] Таблицы создаются в `database/sqlite_db.py` при первом импорте модуля.

Отложенные публикации и черновики хранятся отдельно:

```text
dev/database/scheduled_posts.json
```

## Логи

Ошибки и служебный вывод пишутся в:

```text
bot_errors.log
```

Файл пересоздаётся при старте `dev/main.py`.
