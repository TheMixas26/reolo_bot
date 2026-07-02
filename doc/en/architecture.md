# Architecture

## Entry Point

The main entry point of the project is `dev/main.py`.

It:

- creates `AIService`, `BackgroundScheduler` and the shared `AppContext`;
- loads text resources for enabled plugins;
- registers `CorePlugin` and plugins from the `enabled_plugins` list;
- runs `pytest tests/ -v` before starting bots;
- starts the background scheduler;
- creates separate threads for the main, RPG and bank Telegram bots;
- starts the VK listener if the VK adapter is configured;
- restarts Telegram bot polling when it fails.

## Directory Structure

```text
dev
├── analytics               simple analytics and event logging
├── card_game               domain logic of the card game
├── config.py               local secrets and environment file
├── core                    AppContext and the base core plugin
├── database                SQLite, TinyDB and storage operations
├── handlers                shared Telegram handlers
│   └── card_handlers       Telegram layer of the card game
├── main.py                 entry point
├── plugin_template         template for a new plugin
├── plugins                 feature plugins
├── posting                 models, publishing service and platform adapters
│   └── adapters            Telegram/VK publishing adapters
├── settings.py             non-secret configuration
├── utils                   auxiliary services
└── varibles                text resources and service data
```

## Application Context

`dev/core/context.py` contains `AppContext`. It collects:

- Telegram bot instances;
- the shared `APScheduler`;
- logger and plugin logger factory;
- the `config` object;
- Telegram adapters;
- administrator, channel and service chat IDs;
- `AIService`;
- `PostPublisher` and the administrator target.

Plugins receive `context` in `setup()` and use it to register handlers, jobs and dependencies.

## Plugins

The following plugins are currently connected in `dev/main.py`:

- `CorePlugin` — basic `/start`, `/help`, `/changelog` commands;
- `PredlojkaPlugin` — suggestions, moderation, tags, drafts and scheduled posts;
- `BirthdaysPlugin` — birthdays and notifications;
- `WeatherPlugin` — weather forecasts;
- `AIPlugin` — YandexGPT responses;
- `AdminUtilsPlugin` — backups, bot commands, broadcasts and service actions;
- `BankPlugin` — banking commands;
- `AchievementsPlugin` — achievements;
- `CalendarPlugin` — imperial calendar.

A typical plugin structure:

```text
plugin.py      connection point
handlers.py    commands and callback/message handlers
jobs.py        background jobs
service.py     business logic
db.py          local storage layer, when needed
texts.json     text templates
```

## Publishing

Publishing is located in `dev/posting/`.

- `models.py` describes posts, platforms and publishing targets;
- `services.py` contains `PostPublisher`;
- `runtime.py` builds adapters from `dev/config.py`;
- `adapters/telegram.py` publishes to Telegram;
- `adapters/vk.py` publishes to VK.

Telegram is active by default. VK is added when the config contains `VK_TOKEN` and one destination identifier: `VK_OWNER_ID` or `VK_GROUP_ID`.

## Main Data

The main SQLite database is created at:

```text
dev/database/bot.sqlite3
```

It creates, among others, the following tables:

- `user_accounts`
- `birthdays`
- `rpg_players`
- `achievements`
- `user_achievements`
- `cards`
- `card_packs`
- `inventory`
- `card_events`
- `card_event_rewards`

Scheduled posts and drafts use a separate TinyDB storage:

```text
dev/database/scheduled_posts.json
```

## Background Tasks

Background jobs are registered by plugins through `context.scheduler`.

Currently scheduled:

- scheduled post queue checks;
- daily birthday notifications;
- personal reminders;
- birthday congratulations;
- weather forecasts;
- database backups;
- Telegram command list updates;
- achievement checks;
- imperial calendar event checks.

## Dependencies Between Modules

The general flow is:

- `main.py` builds the context, connects plugins and starts processes;
- `plugins/*` register functionality;
- `handlers/` and `plugins/*/handlers.py` receive Telegram events;
- `posting/` publishes to target platforms;
- `database/` stores SQLite data and the scheduled post queue;
- `card_game/` encapsulates card game mechanics;
- `settings.py` stores public settings;
- `config.py` stores secrets, tokens, chat IDs and bot instances.

Because `config.py` is imported by many modules, it remains a crucial project configuration point.
