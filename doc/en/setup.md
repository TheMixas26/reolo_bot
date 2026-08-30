# Launch and Setup

## Requirements

- Python `3.14+`
- Telegram bot tokens for the needed bots
- Yandex Cloud keys, if `#ai` is used
- VK token, if VK publishing is needed

Installing dependencies:

```bash
pip install -r requirements.txt
```

## Where `config.py` Should Be Located

The project expects a file `dev/config.py`.

This is important for two reasons:

- `dev/main.py` imports `config` as a module from the `dev` directory;
- part of the paths in the code are specified relative to the repository root.

Therefore, run the project this way:

```bash
python dev/main.py
```

Running from the `dev/` directory may lead to incorrect relative paths.

## Where to Change Public Parameters

For public project settings, there is a separate file:

```text
dev/settings.py
```

It includes:

- project and bot names;
- username of the card game bot;
- display names of currencies;
- commission for bank transfers;
- calendar names;
- other branding parameters that should not be considered secrets.

## Example of `dev/config.py`

```python
DEBUG_MODE = True
HIBERNATION = False

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

CATALOG_ID = "{yandex_cloud_catalog_id}"
SECRET_KEY = "{yandex_cloud_api_key}"

# Optional: VK publishing
VK_TOKEN = ""
VK_OWNER_ID = None
VK_GROUP_ID = None
VK_API_VERSION = "5.199"
```

## What is Configured in `config.py`

- `DEBUG_MODE` — launch mode for the test environment;
- `HIBERNATION` — restricted mode for the suggestion bot;
- `PREDLOJKA_TOKEN`, `BANK_TOKEN`, `RPG_TOKEN` — Telegram bot tokens;
- `channel`, `channel_red`, `chat_mishas_den`, `backup_chat` — channel and chat IDs;
- `admin` — Telegram ID of the administrator;
- `location` — coordinates for the weather forecast;
- `CATALOG_ID` and `SECRET_KEY` — YandexGPT settings;
- `VK_TOKEN`, `VK_OWNER_ID`, `VK_GROUP_ID`, `VK_API_VERSION` — optional VK settings.

The transfer commission is set in `dev/settings.py` through `BANK_TRANSFER_COMMISSION`.

The imperial calendar is created inside `dev/plugins/calendar/service.py` and reads JavaScript rules from `dev/utils/imperial_date_generator.js`.

## Launch

From the repository root:

```bash
python dev/main.py
```

On startup:

- `bot_errors.log` is recreated;
- plugin texts are loaded;
- handlers and background jobs are registered;
- tests are run with `python -m pytest tests/ -v`;
- if tests pass, the scheduler starts;
- the main bot, RPG bot and bank bot start;
- the VK listener starts if the VK adapter is configured.

If tests fail, `dev/main.py` exits and bots are not started.

## Database

The main database is created automatically at:

```text
dev/database/bot.sqlite3
```

Tables are created in `database/sqlite_db.py` on first module import.

Scheduled posts and drafts are stored separately:

```text
dev/database/scheduled_posts.json
```

## Logs

Errors and system output are written to:

```text
bot_errors.log
```

The file is recreated when `dev/main.py` starts.
