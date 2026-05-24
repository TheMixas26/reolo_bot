# Architecture

## Entry Point

The main entry point of the project: `dev/main.py`.

It:
- imports handlers to register Telegram commands and callbacks;
- imports `utils.schedulers` to immediately start `APScheduler`;
- creates separate threads for Telegram bots;
- restarts polling when it fails.

## Directory Structure

```text
dev
├── achievements            achievements logic
├── ai                      integration with YandexGPT
├── analytics               simple analytics and event logging 
├── card_game               domain logic of the card game
├── config.py               configuration file
├── database                SQLite and storage operations
├── handlers                telegram handlers for commands and messages
│   ├── card_handlers       telegram layer of the card game
├── main.py                 entry point
├── posting                 posting and moderation handlers
│   ├── adapters            adapters for posting to different channels
├── settings.py             non-secret configuration
├── utils                   auxiliary services and scheduler
└── varibles                text resources and service data
```

## Main Modules

### `handlers/`

Contains the application-level Telegram layer:

- `predlojka_handlers.py` — sending posts, moderation, tags `#анон`, `#вопрос`, `#ai`;
- `admin_handlers.py` — administrative commands;
- `user_handlers.py` and `misc_handlers.py` — user commands and help;
- `bank_handlers.py` — banking commands;
- `achievements_handlers.py` — achievements commands;
- `card_handlers/` — commands, callback handlers and UI of the card game.

### `card_game/`

Domain part of the card mini-game:

- models;
- card and pack catalogs;
- game services;
- sessions;
- message formatting;
- battle logic.

### `database/sqlite_db.py`

Central layer of data storage.

Here:

- tables are created;
- base is initialized;
- operations with users, balances, birthdays and card entities are stored.

## Data and Tables

Currently, the database creates, among other things, the following tables:

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

## Background Tasks

The scheduler is located in `dev/utils/schedulers.py`.

It schedules tasks for:

- daily birthday notifications;
- personal reminders;
- weather forecasts;
- database backups;
- achievement checks;
- updates to the list of commands in Telegram.

## Dependencies between modules

The project has a rather straightforward architecture:

- `main.py` starts the entire application;
- `handlers/` work as the Telegram API entry layer;
- `database/sqlite_db.py` handles data storage;
- `utils/` and `achievements/` provide service behavior;
- `card_game/` encapsulates the game mechanics;
- `config.py` links the environment, tokens, chat IDs and bot instances.

Due to the fact that `config.py` is imported by many modules, this file is a crucial point of project configuration.
