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
- provides buttons for publication, rejection, saving as a draft and scheduling.

Publishing goes through `PostPublisher`: by default the post is sent to the Telegram channel, and when the VK adapter is configured it is also published to VK.

## Tags

### `#anon`

Hides the sender. In the current logic, the tag is processed as a service tag and is not published in the post text.

The old alias `#анон` is also supported.

### `#question`

Marks the message as a subscriber question. For such messages, moderation uses a separate publication scenario with an administrator response.

The old alias `#вопрос` is also supported.

### `#ai`

Attempts to call an AI response through the `dev/plugins/ai/` plugin and YandexGPT.

### `#event`

Does not send the message to the regular suggestion queue. Instead, the idea is saved to a text library of events and forwarded to the administrator.

### `#report`

Used for bug reports, typos and other fixes. The message is sent to the administrator outside standard moderation.

### `#message` / `#dm`

Sends a message to the administrator with the ability to reply to the user in private messages.

### `#ignore`

Suppresses the bot's usual response to the user's message.

## Drafts and Scheduled Posts

The administrator can save a submitted post as a draft or choose a date and time for publication.

- scheduled post data is stored in `dev/database/scheduled_posts.json`;
- `/scheduled_posts` shows drafts and scheduled posts;
- the suggestion plugin periodically checks the queue and publishes ready entries.

## Achievements

The achievement system allows:

- storing a list of achievements;
- assigning achievements to users;
- revoking them;
- automatically checking conditions.

Achievement logic is located in `dev/plugins/achievements/`.

## Birthdays

The birthday subsystem can:

- store user birth dates;
- enable personal notifications;
- send daily reminders;
- congratulate users on their birthdays.

The logic is located in `dev/plugins/birthdays/`.

## Weather

The weather module uses `open-meteo` and sends a daily weather summary to the chat.

The logic is located in `dev/plugins/weather/`.

## Imperial Calendar

The calendar plugin shows the current imperial date, nearest holidays and the full event list.

The Python wrapper lives in `dev/plugins/calendar/service.py`, while the calendar rules are defined in `dev/utils/imperial_date_generator.js`.

## Bank

The banking part of the project remains a light game-like mechanic with its own Telegram bot.

Supported:

- viewing balance;
- transfers between users;
- working with currency rates.

The logic is located in `dev/plugins/bank/`.

## Card Game

The project includes a separate card-based mini-game with its own bot.

Supported:

- opening packs;
- card catalog;
- inventory;
- duels;
- team battles;
- card events.

Domain logic is located in `dev/card_game/`, and the Telegram layer is in `dev/handlers/card_handlers/`.

## Analytics and Service Mechanisms

The project logs startup, crash and user-action events through `analytics.stats`. Administrative utilities, backups, command updates and service broadcasts are located in `dev/plugins/admin_utils/`.
