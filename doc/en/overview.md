# Project Overview

`Imperial Suggestion` — this is a set of Telegram bots and service modules for the `Imperial Herald` channel.

Initially, the project was a bot for submitted posts, but over time it has grown into a multifunctional system with several usage scenarios.

## What the project can do

- accepts messages, media, documents and albums for publication;
- sends materials to the administrator for moderation;
- supports special tags like `#anon`, `#question` and `#ai`;
- maintains user profiles, achievements and activity counters;
- stores birthdays and sends notifications;
- publishes weather forecasts;
- launches banking commands and the card-based mini-game;
- stores state in SQLite.

## Project Composition

In the project, three Telegram bots actually work:

- `predlojka_bot` — main channel bot;
- `bank_bot` — separate bank system bot;
- `rpg_bot` — separate card game bot.

Their launch is coordinated through one entrypoint: `dev/main.py`.

## Key Features

### Suggestion

The user sends a message or media, and the bot formats the publication and forwards it to the administrator with confirmation buttons.

### Social Mechanics

The user profile can include balance, achievements, birthdays, and other game elements.

### Automation

Through `APScheduler` the project regularly performs background tasks: notifications, backups, command updates and achievement checks.

## Where to Look Further

- [Launch and Setup](setup.md)
- [Architecture](architecture.md)
- [Bot Functions](features.md)
- [Commands](commands.md)
