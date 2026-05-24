# Launch and Setup

## Requirements

- Python `3.14+`
- Telegram bot tokens for the needed bots
- keys for Yandex Cloud, if `#ai` is used

Installing dependencies:

```bash
pip install -r requirements.txt
```

## Where `config.py` Should Be Located

The project expects a file `dev/config.py`.

This is important for two reasons:

- `dev/main.py` imports `config` as a module from the `dev` directory;
- part of the paths in the code are specified relative to the repository root.

Therefore, to run the project, you should do it exactly this way:

```bash
python dev/main.py
```

Running from the `dev/` directory may lead to incorrect relative paths.

## Where to Change Public Parameters

For public project settings, there is now a separate file:

```text
dev/settings.py
```

It includes:

- project and bot names;
- username of the card game bot;
- display names of currencies;
- commission for bank transfers;
- other branding parameters that should not be considered secrets.

## Example of `dev/config.py`

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

## What is Configured in `config.py`

- `DEBUG_MODE` — launch mode for the test environment;
- `PREDLOJKA_TOKEN`, `BANK_TOKEN`, `RPG_TOKEN` — Telegram bot tokens;
- `channel`, `channel_red`, `chat_mishas_den`, `backup_chat` — channel and chat IDs;
- `admin` — Telegram ID of the administrator;
- `location` — coordinates for the weather forecast;
- `CATALOG_ID` and `SECRET_KEY` — YandexGPT settings.

The transfer commission is now set in `dev/settings.py` through `BANK_TRANSFER_COMMISSION`.

## Launch

From the repository root:

```bash
python dev/main.py
```

When starting:

- the background task scheduler is launched;
- the main proposal bot is started;
- the RPG bot is started;
- the bank bot is started only if `DEBUG_MODE = False`.

## Database

The main database is created automatically at the path:

```text
dev/database/bot.sqlite3
```

Tables are created in `database/sqlite_db.py` on the first run.

## Logs

Errors and system output are written to:

```text
bot_errors.log
```

The file is recreated when `dev/main.py` is started.
