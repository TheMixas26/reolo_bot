# Bot Features

## Suggestion and Moderation

The main bot accepts:

- text;
- photos;
- videos;
- documents;
- audio;
- voice messages;
- stickers;
- forwarded posts;
- albums (`media groups`).

After receiving the message, the bot:

- prepares the publication text;
- adds the author's signature or an anonymous marker;
- sends a preview to the administrator;
- provides buttons for publication or rejection.

## Tags

### `#anon`

Hides the sender. In the current logic, the tag is processed as a service tag and is not published in the post text.

### `#question`

Marks the message as a subscriber's question. For such messages, moderation uses a separate publication scenario with an admin response.

### `#ai`

Attempts to call an AI response through the `ai/ai_module.py` module.

### `#event`

Does not send the message to the regular suggestion box. Instead, the idea is saved to a text library of events and forwarded to the administrator.

### `#report`

Used for bug reports, typos and other fixes. The message is sent to the administrator outside the standard moderation.

### `#message` / `#dm`

Sends a message to the administrator with the ability to reply to the user in private messages.

### `#ignore`

Suppresses the bot's usual response to the user's message.

## Achievements

The achievement system allows:

- storing a list of achievements;
- assigning achievements to users;
- revoking them;
- automatically checking conditions.

Part of the logic is located in `dev/achievements/achievement_system.py`, and the commands are moved to `dev/handlers/achievements_handlers.py`.

## Birthdays

The birthday subsystem can:

- store user birth dates;
- enable personal notifications;
- send daily reminders;
- congratulate birthdays.

## Weather

The weather module uses `open-meteo` and sends a daily summary with weather information to the chat.

## Bank

The banking part of the project remains simplified and closer to fan mechanics.

Supported:

- viewing balance;
- transfers between users;
- working with currency rates.

## Card Game

The project includes a separate card-based mini-game with its own bot.

Supported:

- opening packs;
- card catalog;
- inventory;
- duels;
- team battles;
- card events.

## Analytics and Service Mechanisms

The project also tracks launch and error events, with some actions logged through `analytics.stats`.
