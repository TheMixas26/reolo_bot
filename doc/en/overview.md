# Project Overview

`Imperial Suggestion` is a set of Telegram bots, service modules and publishing adapters for the `Imperial Herald` channel.

The project started as a submitted-post bot, but it has grown into a multifunctional system with moderation, automation, game mechanics and plugin-based code organization.

## What the project can do

- accepts text, media, documents, forwarded posts and albums for publication;
- sends materials to the administrator for moderation;
- supports publishing to Telegram and, when configured, VK;
- can save drafts and schedule posts;
- supports service tags like `#anon`, `#question`, `#ai`, `#event`, `#report`, `#dm`;
- maintains user profiles, achievements and activity counters;
- stores birthdays and sends notifications;
- publishes weather forecasts;
- shows imperial calendar dates and events;
- launches banking commands and the card-based mini-game;
- stores main state in SQLite.

## Project Composition

The project runs three Telegram bots:

- `predlojka_bot` — the main channel and suggestion bot;
- `bank_bot` — a separate bot for the bank system;
- `rpg_bot` — a separate bot for the card game.

Their launch is coordinated through one entrypoint: `dev/main.py`.

The project can also connect a VK adapter. It is used to publish posts to a VK wall when `VK_TOKEN` and `VK_OWNER_ID` or `VK_GROUP_ID` are set in `dev/config.py`.

## Key Scenarios

### Suggestions

The user sends a message or media, and the bot formats the publication and forwards it to the administrator with buttons for approval, rejection, saving as a draft or scheduling.

### Social Mechanics

The user profile can include balance, achievements, birthdays and other game elements.

### Automation

Through `APScheduler`, the project regularly performs background tasks: notifications, backups, command updates, achievement checks, weather reports and calendar notifications.

### Plugins

Features are grouped into plugins under `dev/plugins/`. Each plugin registers its own handlers and, when needed, background jobs through the shared `AppContext`.

## Where to Look Further

- [Launch and Setup](setup.md)
- [Architecture](architecture.md)
- [Bot Features](features.md)
- [Commands](commands.md)
